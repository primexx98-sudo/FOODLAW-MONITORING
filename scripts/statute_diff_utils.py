"""법령자료 조문 파싱 + 버전 간 diff 계산.

law.go.kr Open API 응답에서 법령(target=law)과 행정규칙(target=admrul)은 조문 구조가
서로 다르다 (law는 조문번호/제목/본문이 분리된 구조체 배열 + 조문변경여부 플래그를 주고,
admrul은 "제N조(제목)...본문" 형태의 통짜 문자열 배열만 준다) — 이 차이를 여기서 흡수해
양쪽 다 동일한 {no, title, text} 형태로 정규화한 뒤 diff 로직은 공유한다.
"""

import difflib
import re

ARTICLE_NO_RE = re.compile(r"^제(\d+)조(?:의(\d+))?\s*(?:\(([^)]*)\))?")


def parse_admrul_article(raw_text: str) -> dict:
    """'제2조(정의) 이 고시에서...' 형태의 통짜 문자열을 {no, title, text}로 분해."""
    m = ARTICLE_NO_RE.match(raw_text.strip())
    if not m:
        return {"no": "", "title": "", "text": raw_text}
    no = m.group(1) + (f"의{m.group(2)}" if m.group(2) else "")
    title = m.group(3) or ""
    return {"no": no, "title": title, "text": raw_text}


def normalize_law_articles(jomun_units: list) -> list:
    """target=law lawService.do 응답의 법령.조문.조문단위 배열을 정규화."""
    articles = []
    for unit in jomun_units:
        if unit.get("조문여부") != "조문":
            continue  # 장/절 제목 등 조문이 아닌 구분자는 제외
        articles.append({
            "no": unit.get("조문번호", ""),
            "title": unit.get("조문제목", ""),
            "text": unit.get("조문내용", ""),
            "changed_flag": unit.get("조문변경여부") == "Y",
        })
    return articles


_NO_TEXT_MARKERS = ("버튼을 이용", "상단 메뉴")


def normalize_admrul_articles(jomun_content) -> list:
    """target=admrul lawService.do 응답의 AdmRulService.조문내용을 정규화.

    이 필드는 고시마다 형태가 다르다:
    - "제N조(제목)..." 문자열의 리스트 (조문 형식을 갖춘 일반 고시)
    - 빈 문자열 또는 "자세한 내용은 상단 메뉴...버튼을 이용" 안내문 (본문 자체를 API가
      안 주는 방대한 공전류 — 실측: 건강기능식품의 기준 및 규격, 식품첨가물의 기준 및 규격)
    - "Ⅰ. 총칙..." 처럼 조문(제N조) 형식이 아니라 장/절 텍스트 통짜 문자열 (실측:
      식품등의 표시기준) — 조문 단위 diff는 못 하지만 검색·전문 표시용으로는 유효한 텍스트
    """
    if isinstance(jomun_content, list):
        return [parse_admrul_article(raw) for raw in jomun_content]

    text = (jomun_content or "").strip()
    if not text or any(marker in text for marker in _NO_TEXT_MARKERS):
        return []
    return [{"no": "", "title": "전문", "text": text}]


def diff_articles(old_articles: list, new_articles: list, *, line_diff: bool = False,
                   sort_numeric: bool = True) -> list:
    """no(조문번호 또는 별표키) 기준으로 이전/현재를 매칭해 변경 목록을 만든다.

    law target은 API의 changed_flag를 신뢰 신호로 병기하되, admrul처럼 flag가 없는
    경우도 동일하게 처리되도록 최종 판단은 항상 텍스트 비교로 내린다 — 여러 버전을
    건너뛰었을 때 flag만으로는 그 사이 누적 변경을 못 잡을 수 있기 때문.

    별표(annex)는 no가 "별표키"(예: "000100E")라 조문번호처럼 숫자로 깔끔하게 정렬되지
    않으므로 `sort_numeric=False`로 호출해 원래 등장 순서를 유지한다. 별표 본문은 줄바꿈이
    이미 의미 있는 표 구조라 문장 단위(`_split_sentences`) 대신 줄 단위로 diff해야
    (`line_diff=True`) 표가 깨지지 않는다.
    """
    old_by_no = {a["no"]: a for a in old_articles if a["no"]}
    new_by_no = {a["no"]: a for a in new_articles if a["no"]}
    diff_fn = unified_line_diff if line_diff else unified_text_diff

    changes = []
    for no, new_a in new_by_no.items():
        old_a = old_by_no.get(no)
        if old_a is None:
            changes.append({
                "article_no": no, "title": new_a["title"], "change_type": "added",
                "old_text": "", "new_text": new_a["text"],
            })
        elif old_a["text"] != new_a["text"]:
            changes.append({
                "article_no": no, "title": new_a["title"], "change_type": "modified",
                "old_text": old_a["text"], "new_text": new_a["text"],
                "diff_lines": diff_fn(old_a["text"], new_a["text"]),
            })
    for no, old_a in old_by_no.items():
        if no not in new_by_no:
            changes.append({
                "article_no": no, "title": old_a["title"], "change_type": "removed",
                "old_text": old_a["text"], "new_text": "",
            })

    if sort_numeric:
        changes.sort(key=_article_sort_key)
    return changes


def _article_sort_key(change: dict):
    m = re.match(r"(\d+)(?:의(\d+))?", change["article_no"])
    if not m:
        return (9999, 0)
    return (int(m.group(1)), int(m.group(2) or 0))


def unified_text_diff(old_text: str, new_text: str) -> list:
    """한 조문 내부의 문장 단위 변경을 보여주기 위한 간단한 라인 diff."""
    old_lines = _split_sentences(old_text)
    new_lines = _split_sentences(new_text)
    matcher = difflib.SequenceMatcher(a=old_lines, b=new_lines)
    result = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if tag in ("delete", "replace"):
            for line in old_lines[i1:i2]:
                result.append({"type": "removed", "text": line})
        if tag in ("insert", "replace"):
            for line in new_lines[j1:j2]:
                result.append({"type": "added", "text": line})
    return result


def _split_sentences(text: str) -> list:
    parts = re.split(r"(?<=[.!?다\)])\s+", text.strip())
    return [p for p in parts if p]


def unified_line_diff(old_text: str, new_text: str) -> list:
    """별표처럼 줄바꿈 자체가 표 구조인 텍스트용 — 문장 단위가 아니라 원래 줄 단위로 diff."""
    old_lines = old_text.split("\n")
    new_lines = new_text.split("\n")
    matcher = difflib.SequenceMatcher(a=old_lines, b=new_lines)
    result = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if tag in ("delete", "replace"):
            for line in old_lines[i1:i2]:
                result.append({"type": "removed", "text": line})
        if tag in ("insert", "replace"):
            for line in new_lines[j1:j2]:
                result.append({"type": "added", "text": line})
    return result


def normalize_annexes(byl_field) -> list:
    """target=law/admrul 공통 — lawService.do 응답의 '별표' 필드(별표.별표단위)를 정규화.

    법령·고시 API 모두 조문과 별개로 별표(표 형식 첨부)의 텍스트를 이미 제공한다는 걸
    뒤늦게 발견함 — 이전엔 별표를 PDF/HWP 원문 링크로만 다룰 수 있다고 판단했었음
    (실측: 원산지 표시대상처럼 조문 본문엔 없고 별표에만 있는 정보가 이 필드로 확보됨).
    '별표번호'는 별표 1과 별표 1의2가 같은 값("0001")으로 나오는 등 신뢰할 수 없어
    개별 첨부를 구분하는 고유 식별자로 '별표키'를 쓴다.
    """
    if not isinstance(byl_field, dict):
        return []
    units = byl_field.get("별표단위", [])
    if isinstance(units, dict):
        units = [units]

    annexes = []
    for u in units:
        raw_content = u.get("별표내용", [])
        lines = []
        for chunk in raw_content:
            if isinstance(chunk, list):
                lines.extend(chunk)
        annexes.append({
            "no": u.get("별표키", ""),
            "title": u.get("별표제목", ""),
            "text": "\n".join(lines),
        })
    return annexes
