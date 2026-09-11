"""'법령자료' 탭 데이터 수집 — 지정 법령·고시(statute_config.STATUTES)의 최신 원문을 받아
이전에 저장해둔 버전과 비교, 바뀌었으면 조문 단위 diff를 만들어 data/statute_library.json에 쌓는다.

법령 모니터(collect_lawgokr.py)의 키워드 검색과 달리, 여기는 "이 법령들의 최신 상태를
항상 최신으로 유지"가 목적이라 고정 리스트 기반이다.

API 키는 환경변수 LAW_API_KEY(OC)에서 읽는다.
"""

import json
import os
import re
import sys
from datetime import datetime, timezone

import requests

sys.path.insert(0, os.path.dirname(__file__))
from statute_config import STATUTES, MAX_HISTORY_PER_STATUTE, CODEX_FULLTEXT_KEYS
from statute_diff_utils import (
    normalize_law_articles,
    normalize_admrul_articles,
    normalize_annexes,
    normalize_revision_reason,
    normalize_attachments,
    diff_articles,
)
from hwpx_extract import extract_codex_fulltext, pick_hwpx_attachment

API_KEY = os.environ.get("LAW_API_KEY", "")
SEARCH_URL = "https://www.law.go.kr/DRF/lawSearch.do"
SERVICE_URL = "https://www.law.go.kr/DRF/lawService.do"

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "statute_library.json")


_DOT_VARIANTS_RE = re.compile(r"[ㆍ·‧⋅∙]")


def _normalize_name(name: str) -> str:
    """법령·고시명의 '가운뎃점' 표기가 소관부처마다 다른 유니코드 문자를 섞어 쓴다
    (실측: 'ㆍ'(U+318D)와 '·'(U+00B7)가 같은 목적으로 혼용됨) — 비교 전에 통일."""
    return _DOT_VARIANTS_RE.sub("·", name).strip()


def _pick_exact_match(results: list, name_field: str, expected_name: str) -> dict | None:
    """law.go.kr 검색은 부분/형태소 매칭이라 관련 없는 법령·고시가 같이 걸리고 순서도
    관련도순이 아니다 (실측: '건강기능식품의 기준 및 규격' 검색 시 서로 다른 고시 2건이
    나오고, 'sort=date'를 줘도 날짜순으로 정렬되지 않음) — 반드시 이름이 정확히 일치하는
    항목만 채택하고, 없으면 포기한다(오매칭으로 엉뚱한 법령을 저장하는 것보다 안전)."""
    target = _normalize_name(expected_name)
    for r in results:
        if _normalize_name(r.get(name_field, "")) == target:
            return r
    return None


def search_current(statute: dict) -> dict | None:
    """target별 검색 API를 호출해 최신 버전의 ID/일련번호·공포·시행 정보를 가져온다."""
    target = statute["api_target"]
    params = {"OC": API_KEY, "target": target, "type": "JSON", "query": statute["query"],
              "display": 20}
    r = requests.get(SEARCH_URL, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()

    if target == "law":
        results = data.get("LawSearch", {}).get("law", [])
        results = [results] if isinstance(results, dict) else results
        law = _pick_exact_match(results, "법령명한글", statute["name"])
        if law is None:
            print(f"[법령자료] '{statute['name']}' 검색결과 중 이름이 정확히 일치하는 항목 없음 "
                  f"({len(results)}건 조회됨)")
            return None
        return {
            "detail_id": law.get("법령ID", ""),
            "version_id": law.get("법령일련번호", ""),
            "promulgation_no": law.get("공포번호", ""),
            "promulgation_date": law.get("공포일자", ""),
            "effective_date": law.get("시행일자", ""),
        }
    else:  # admrul
        results = data.get("AdmRulSearch", {}).get("admrul", [])
        results = [results] if isinstance(results, dict) else results
        rule = _pick_exact_match(results, "행정규칙명", statute["name"])
        if rule is None:
            print(f"[법령자료] '{statute['name']}' 검색결과 중 이름이 정확히 일치하는 항목 없음 "
                  f"({len(results)}건 조회됨)")
            return None
        return {
            "detail_id": rule.get("행정규칙ID", ""),
            "version_id": rule.get("행정규칙일련번호", ""),
            "promulgation_no": rule.get("발령번호", ""),
            "promulgation_date": rule.get("발령일자", ""),
            "effective_date": rule.get("시행일자", ""),
        }


def fetch_detail(statute: dict, version_id: str) -> dict:
    """조문과 별표를 한 번의 API 호출로 함께 가져온다 — 응답 하나에 둘 다 들어있다는 걸
    뒤늦게 발견해서(원래는 별표를 PDF 링크로만 다룰 수 있다고 판단했었음), 별도 호출을
    추가하는 대신 기존 호출의 응답을 더 활용하도록 함(호출 수가 배로 늘면 CI에서 이미
    느린 수집 시간이 더 늘어남).

    항상 실제로 조회를 시도한다 — 방대한 공전류처럼 API가 조문 본문을 안 주는 경우도
    있지만, 그건 응답을 받아본 뒤에야 알 수 있어(normalize 단계에서 빈 리스트로 판정)
    설정값만으로 미리 건너뛰면 잘못된 예외 처리가 굳어질 위험이 있다."""
    target = statute["api_target"]
    id_param = {"MST": version_id} if target == "law" else {"ID": version_id}
    params = {"OC": API_KEY, "target": target, "type": "JSON", **id_param}
    r = requests.get(SERVICE_URL, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()

    if target == "law":
        law = data.get("법령", {})
        jomun = law.get("조문", {}).get("조문단위", [])
        return {
            "articles": normalize_law_articles(jomun), "annexes": normalize_annexes(law.get("별표")),
            "revision_reason": "", "attachments": [],
        }
    else:
        service = data.get("AdmRulService", {})
        jomun = service.get("조문내용", [])
        return {
            "articles": normalize_admrul_articles(jomun), "annexes": normalize_annexes(service.get("별표")),
            # "공전"류(조문 본문 미제공)에서 diff 대신 보여줄 정보 — 조문이 있는 일반 고시엔
            # 불필요하지만, 항상 채워둬도 해가 없고 어느 게 공전류로 새로 밝혀지든 바로 쓸 수 있음.
            "revision_reason": normalize_revision_reason(service.get("제개정이유")),
            "attachments": normalize_attachments(service.get("첨부파일")),
        }


def fetch_codex_fulltext(attachments: list) -> str:
    """CODEX_FULLTEXT_KEYS 대상(공전 중 HWPX 첨부를 가진 2종)의 첨부파일을 내려받아
    검색용 전문 텍스트를 뽑는다. 실패해도(다운로드 오류·예상 밖 파일 구조 등) 전체
    수집을 중단시키지 않고 빈 문자열로 대체 — 이 텍스트는 AI 의미검색 인덱싱용
    부가 정보일 뿐, 없어도 사이트의 다른 기능엔 영향 없음."""
    attachment = pick_hwpx_attachment(attachments)
    if attachment is None:
        return ""
    try:
        r = requests.get(attachment["url"], timeout=60)
        r.raise_for_status()
        return extract_codex_fulltext(r.content)
    except Exception as e:
        print(f"[법령자료] 공전 전문 추출 실패({attachment.get('name', '')}): {e}")
        return ""


def detail_url(statute: dict) -> str:
    prefix = "법령" if statute["api_target"] == "law" else "행정규칙"
    return f"https://www.law.go.kr/{prefix}/{statute['name']}"


def load_library() -> dict:
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"statutes": []}


def save_library(library: dict):
    library["generated_at"] = datetime.now(timezone.utc).isoformat()
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(library, f, ensure_ascii=False, indent=2)


def collect():
    if not API_KEY:
        print("[법령자료] LAW_API_KEY 환경변수가 설정되지 않았습니다. 건너뜁니다.")
        return

    library = load_library()
    by_key = {s["key"]: s for s in library["statutes"]}
    now = datetime.now(timezone.utc).isoformat()

    for statute in STATUTES:
        key = statute["key"]
        try:
            meta = search_current(statute)
        except Exception as e:
            print(f"[법령자료] '{statute['name']}' 검색 오류: {e}")
            continue

        if meta is None:
            print(f"[법령자료] '{statute['name']}' 검색 결과 없음")
            continue

        prev = by_key.get(key)
        prev_current = prev.get("current") if prev else None
        version_changed = prev_current is None or prev_current.get("version_id") != meta["version_id"]

        if not version_changed:
            # 버전이 그대로라도 name/category는 매번 STATUTES(설정)에서 동기화 — 이전엔
            # 신규 등록 시점에만 채워져서, 이미 추적 중인 항목의 category를 설정에서
            # 바꿔도(예: 공전류를 "기준규격"으로 재분류) 실제 버전 개정이 일어나기 전까지
            # 데이터에 반영 안 되는 문제가 있었음(실측: hff_standard_spec/food_additive_standard
            # 재분류가 다음 개정 때까지 조용히 무시될 뻔함).
            if prev is not None and (prev.get("category") != statute["category"] or prev.get("name") != statute["name"]):
                prev["category"] = statute["category"]
                prev["name"] = statute["name"]
                print(f"[법령자료] '{statute['name']}' 메타데이터만 동기화(category/name)")
            print(f"[법령자료] '{statute['name']}' 변경 없음 (버전 {meta['version_id']})")
            continue

        try:
            detail = fetch_detail(statute, meta["version_id"])
        except Exception as e:
            print(f"[법령자료] '{statute['name']}' 본문 조회 오류: {e}")
            continue

        new_articles = detail["articles"]
        new_annexes = detail["annexes"]
        new_revision_reason = detail.get("revision_reason", "")
        new_attachments = detail.get("attachments", [])
        text_available = bool(new_articles)
        entry = by_key.get(key) or {
            "key": key, "name": statute["name"], "category": statute["category"],
            "api_target": statute["api_target"], "history": [],
        }
        entry["name"] = statute["name"]
        entry["category"] = statute["category"]
        entry["text_available"] = text_available

        if prev_current is None:
            print(f"[법령자료] '{statute['name']}' 신규 등록 (조문 {len(new_articles)}건, 별표 {len(new_annexes)}건)")
        else:
            article_changes = diff_articles(prev_current.get("articles", []), new_articles) if text_available else []
            annex_changes = diff_articles(prev_current.get("annexes", []), new_annexes,
                                           line_diff=True, sort_numeric=False)
            # "공전"류는 조문·별표 모두 API가 본문을 안 줘 diff가 항상 빈 리스트로 나온다 —
            # 그렇다고 버전이 바뀐 사실 자체를 기록 안 하면 개정이 조용히 사라지므로,
            # 조문 diff는 없어도 제개정이유가 있으면 그걸로 대체해 이력에 남긴다.
            reason_only = not (article_changes or annex_changes) and bool(new_revision_reason)
            if article_changes or annex_changes or reason_only:
                entry["history"].insert(0, {
                    "version_id": prev_current.get("version_id"),
                    "effective_date": prev_current.get("effective_date"),
                    "detected_at": now,
                    "article_changes": article_changes,
                    "annex_changes": annex_changes,
                    "revision_reason": new_revision_reason if reason_only else "",
                })
                entry["history"] = entry["history"][:MAX_HISTORY_PER_STATUTE]
                if reason_only:
                    print(f"[법령자료] '{statute['name']}' 개정 감지 — 조문 diff 미제공, 제개정이유로 대체 기록")
                else:
                    print(f"[법령자료] '{statute['name']}' 개정 감지 — 조문 {len(article_changes)}건, "
                          f"별표 {len(annex_changes)}건 변경")

        new_full_text = ""
        if key in CODEX_FULLTEXT_KEYS:
            new_full_text = fetch_codex_fulltext(new_attachments)
            print(f"[법령자료] '{statute['name']}' 전문 텍스트 추출 {len(new_full_text)}자"
                  f"{'(검색용, 조문 diff 아님)' if new_full_text else ' — 실패, 링크만 유지'}")

        entry["current"] = {
            "version_id": meta["version_id"],
            "detail_id": meta["detail_id"],
            "promulgation_no": meta["promulgation_no"],
            "promulgation_date": meta["promulgation_date"],
            "effective_date": meta["effective_date"],
            "revision_reason": new_revision_reason,
            "attachments": new_attachments,
            "full_text": new_full_text,
            "fetched_at": now,
            "detail_url": detail_url(statute),
            "articles": new_articles,
            "annexes": new_annexes,
        }
        by_key[key] = entry

    # STATUTES에 정의된 순서를 그대로 유지 (카테고리별 그룹핑에 사용)
    library["statutes"] = [by_key[s["key"]] for s in STATUTES if s["key"] in by_key]
    save_library(library)
    print(f"\n법령자료 수집 완료: {len(library['statutes'])}건 처리")


if __name__ == "__main__":
    collect()
