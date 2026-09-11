"""HWPX(한글 2014+ XML/ZIP 포맷) 첨부파일에서 검색용 전문 텍스트를 뽑는다.

"공전"류(건강기능식품/식품첨가물의 기준 및 규격 등, [[statute_config.CODEX_FULLTEXT_KEYS]])는
law.go.kr API가 조문 본문을 안 주는 대신 고시 전문 첨부파일(ZIP/HWPX/PDF)을 제공한다 —
그중 PDF는 실측 결과 한글 단어 사이 공백이 아예 없이 붙어서 추출돼(예: "적색리트머스지를쓴다")
읽기 힘들고 신뢰할 수 없었던 반면, HWPX는 XML이라 문단(<hp:p>)·텍스트런(<hp:t>) 구조를
그대로 따라가면 공백이 보존된 읽을 수 있는 텍스트가 나온다는 걸 실측으로 확인 — 그래서
PDF는 포기하고 HWPX만 사용한다. 조문 단위 diff는 여전히 불가능(품목이 표로 나열된 구조라
"제N조" 경계가 없음) — 검색(AI 의미검색 임베딩)용 원문 확보가 목적.
"""

import io
import xml.etree.ElementTree as ET
import zipfile


def extract_hwpx_text(hwpx_bytes: bytes) -> str:
    """HWPX 파일 하나(zip 컨테이너, Contents/section*.xml에 본문)에서 읽기 순서대로
    본문 텍스트를 뽑는다. 표 셀이 <hp:t> 안에 <hp:subList>로 깊이 중첩되는 경우가 있는데,
    ElementTree의 .iter()는 모든 element를 정확히 한 번씩 방문하므로 각 <hp:t>의
    **직접 소유 텍스트만**(자손 <hp:t>의 텍스트는 그 자손이 자기 차례에 따로 처리) 모으면
    중복 없이 전체를 커버한다."""
    z = zipfile.ZipFile(io.BytesIO(hwpx_bytes))
    section_names = sorted(n for n in z.namelist() if n.startswith("Contents/section") and n.endswith(".xml"))
    parts = []
    for name in section_names:
        root = ET.fromstring(z.read(name))
        for elem in root.iter():
            local = elem.tag.rsplit("}", 1)[-1]
            if local == "p":
                parts.append("\n")
            elif local == "t" and elem.text:
                parts.append(elem.text)
    return "".join(parts).strip()


def extract_codex_fulltext(attachment_bytes: bytes) -> str:
    """공전 첨부파일에서 전문 텍스트를 뽑는다 — 첨부 자체가 HWPX 단일 파일인 경우와,
    여러 HWPX(+.hwp/.xlsx 등)를 담은 ZIP 컨테이너인 경우 둘 다 지원한다. 컨테이너 안의
    .hwpx만 골라 읽고, 구형 .hwp(바이너리, 파서 없음)·.xlsx 등은 조용히 건너뛴다 —
    **부분 추출**이라 일부 챕터가 이 결과에서 빠질 수 있음을 호출부가 인지하고 있어야 함."""
    z = zipfile.ZipFile(io.BytesIO(attachment_bytes))
    names = z.namelist()
    if any(n.startswith("Contents/section") for n in names):
        return extract_hwpx_text(attachment_bytes)
    parts = []
    for info in z.infolist():
        if info.filename.lower().endswith(".hwpx"):
            parts.append(extract_hwpx_text(z.read(info)))
    return "\n\n".join(p for p in parts if p)


def pick_hwpx_attachment(attachments: list) -> dict | None:
    """첨부파일 목록(collect_statutes.normalize_attachments 결과)에서 HWPX 소스를
    담고 있을 법한 항목을 고른다 — 단일 .hwpx 또는 여러 파일을 담은 .zip."""
    for a in attachments:
        name = (a.get("name") or "").lower()
        if name.endswith(".hwpx") or name.endswith(".zip"):
            return a
    return None
