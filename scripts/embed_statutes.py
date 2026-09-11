"""법령자료 조문·별표를 임베딩해 docs/statute/embeddings.json에 저장 — 브라우저의
"AI 의미검색"이 쓰는 벡터 인덱스를 빌드타임(GitHub Actions)에 미리 만들어둔다.

API 방식(Groq/Gemini 등)을 안 쓰는 이유: 이 사이트는 완전 정적(GitHub Pages, 서버
없음)이고 검색 시점마다 AI를 호출하면 방문자 트래픽에 따라 API 일일 한도에 걸릴 수
있음 — 대신 로컬 오픈소스 임베딩 모델을 여기(빌드타임)와 브라우저(검색 시점) 양쪽에서
"정확히 같은 ONNX 파일"로 돌려서 API 호출 자체를 없앤다. 브라우저 쪽은
build_statute_site.py가 생성하는 <script type="module"> 안에서 @huggingface/transformers로
동일 모델(Xenova/multilingual-e5-small)을 로드한다 — 모델을 바꾸면 반드시 양쪽을 함께 바꿀 것.

무거운 torch/sentence-transformers 대신 onnxruntime+tokenizers만 사용(CI 설치 시간 최소화).
"""

import base64
import json
import os
import struct

import numpy as np
import onnxruntime as ort
import requests
from tokenizers import Tokenizer

MODEL_REPO = "Xenova/multilingual-e5-small"
MODEL_FILES = {
    "model.onnx": f"https://huggingface.co/{MODEL_REPO}/resolve/main/onnx/model_quantized.onnx",
    "tokenizer.json": f"https://huggingface.co/{MODEL_REPO}/resolve/main/tokenizer.json",
}
DIM = 384
MAX_CHUNK_CHARS = 800  # 대략 512토큰 한도 안쪽으로 넉넉히 잡은 문자수 캡(한국어 기준 보수적으로)

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "statute_library.json")
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "docs", "statute", "embeddings.json")
CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "_embed_model_cache")


def ensure_model_files() -> tuple[str, str]:
    os.makedirs(CACHE_DIR, exist_ok=True)
    paths = {}
    for filename, url in MODEL_FILES.items():
        path = os.path.join(CACHE_DIR, filename)
        if not os.path.exists(path):
            print(f"[임베딩] {filename} 다운로드 중... ({url})")
            r = requests.get(url, timeout=120)
            r.raise_for_status()
            with open(path, "wb") as f:
                f.write(r.content)
        paths[filename] = path
    return paths["model.onnx"], paths["tokenizer.json"]


def chunk_text(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list:
    """줄 경계를 존중해 max_chars 안쪽으로 텍스트를 나눈다 — 별표(표 형식)가 대상.
    짧은 조문은 애초에 한 청크로 끝나 이 분할이 거의 발동하지 않는다."""
    lines = text.split("\n")
    chunks, buf, buf_len = [], [], 0
    for line in lines:
        if buf and buf_len + len(line) + 1 > max_chars:
            chunks.append("\n".join(buf))
            buf, buf_len = [], 0
        buf.append(line)
        buf_len += len(line) + 1
    if buf:
        chunks.append("\n".join(buf))
    return chunks or [text]


def build_chunk_list(library: dict) -> list:
    """{key, kind, no, part, text} 형태로 임베딩할 청크 전부를 모은다.
    part는 같은 조문/별표가 여러 청크로 쪼개졌을 때의 순번(브라우저 쪽에서 같은
    법령·고시로 되돌아가기만 하면 되므로 no가 같아도 검색 결과 매칭엔 지장 없음)."""
    chunks = []
    for statute in library["statutes"]:
        cur = statute["current"]
        for a in cur.get("articles", []):
            if not a.get("text"):
                continue
            for part, piece in enumerate(chunk_text(a["text"])):
                chunks.append({"key": statute["key"], "kind": "article", "no": a["no"], "part": part, "text": piece})
        for a in cur.get("annexes", []):
            if not a.get("text"):
                continue
            for part, piece in enumerate(chunk_text(a["text"])):
                chunks.append({"key": statute["key"], "kind": "annex", "no": a["no"], "part": part, "text": piece})
        # "공전"류(조문 본문 미제공) 중 HWPX 첨부에서 뽑은 전문 텍스트(hwpx_extract.py) —
        # kind="fulltext"엔 DOM에 대응하는 <details>가 없어(카드에 원문을 통째로 넣으면
        # 페이지가 수 MB 불어남, [[project_food_law_monitor]] 09-11 참고) jumpToChunk()가
        # 열어젖힐 세부 항목은 없지만, 카드 자체로 스크롤은 정상 동작(기존 로직이 detail이
        # 없으면 그 부분만 건너뛰도록 이미 방어돼 있음) — AI 의미검색으로 "이 공전에 관련
        # 내용이 있다"는 것만 찾아주는 용도.
        full_text = cur.get("full_text", "")
        if full_text:
            for part, piece in enumerate(chunk_text(full_text)):
                chunks.append({"key": statute["key"], "kind": "fulltext", "no": "", "part": part, "text": piece})
    return chunks


def embed_batch(sess, tokenizer, texts: list) -> np.ndarray:
    encs = tokenizer.encode_batch(texts)
    max_len = max(len(e.ids) for e in encs)
    input_ids = np.zeros((len(texts), max_len), dtype=np.int64)
    attn = np.zeros((len(texts), max_len), dtype=np.int64)
    for i, e in enumerate(encs):
        n = len(e.ids)
        input_ids[i, :n] = e.ids
        attn[i, :n] = e.attention_mask
    token_type = np.zeros_like(input_ids)
    out = sess.run(["last_hidden_state"],
                    {"input_ids": input_ids, "attention_mask": attn, "token_type_ids": token_type})[0]
    mask = attn[:, :, None].astype(np.float32)
    mean_pooled = (out * mask).sum(axis=1) / mask.sum(axis=1)
    return mean_pooled / np.linalg.norm(mean_pooled, axis=1, keepdims=True)


def vec_to_b64(vec: np.ndarray) -> str:
    return base64.b64encode(struct.pack(f"<{len(vec)}f", *vec.tolist())).decode("ascii")


def embed():
    if not os.path.exists(DATA_PATH):
        print("[임베딩] statute_library.json이 없습니다. 건너뜁니다.")
        return

    with open(DATA_PATH, encoding="utf-8") as f:
        library = json.load(f)

    chunk_meta = build_chunk_list(library)
    if not chunk_meta:
        print("[임베딩] 임베딩할 청크가 없습니다.")
        return

    model_path, tokenizer_path = ensure_model_files()
    tokenizer = Tokenizer.from_file(tokenizer_path)
    tokenizer.enable_truncation(max_length=512)
    sess = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])

    BATCH = 16
    out_chunks = []
    for i in range(0, len(chunk_meta), BATCH):
        batch = chunk_meta[i:i + BATCH]
        texts = ["passage: " + c["text"] for c in batch]
        vecs = embed_batch(sess, tokenizer, texts)
        for c, v in zip(batch, vecs):
            out_chunks.append({"key": c["key"], "kind": c["kind"], "no": c["no"], "part": c["part"], "vec": vec_to_b64(v)})
        print(f"[임베딩] {min(i + BATCH, len(chunk_meta))}/{len(chunk_meta)} 청크 처리")

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump({"model": MODEL_REPO, "dim": DIM, "chunks": out_chunks}, f)

    print(f"\n임베딩 완료: {len(out_chunks)}개 청크 → {OUT_PATH}")


if __name__ == "__main__":
    embed()
