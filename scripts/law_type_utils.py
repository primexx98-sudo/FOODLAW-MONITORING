"""법령 유형(law_type) 판별 + 식품 관련성 필터 — 3개 수집기(collect_lawgokr/mfds/foodsafety)가 공유.

MFDS(식약처) 게시판은 식품뿐 아니라 의약품·의료기기·화장품·마약류도 함께 다루므로,
제목만으로 식품 관련 여부를 걸러내지 않으면 무관한 항목이 섞여 들어온다.
"""

FOOD_RELEVANT_TERMS = [
    "식품", "건강기능식품", "축산물", "식품위생", "식품표시", "식품안전",
    "기능성", "건기식", "잔류농약", "식품첨가물", "식품등의 표시",
]

# 명백히 식품과 무관한 MFDS 소관 분야 — 이 단어가 있으면 식품 키워드가 있어도 제외
FOOD_EXCLUDE_TERMS = [
    "의약품", "의료기기", "화장품", "마약류", "첨단바이오", "혈액", "장기등", "인체조직", "체외진단",
]


def is_food_related(title: str) -> bool:
    if any(term in title for term in FOOD_EXCLUDE_TERMS):
        return False
    return any(term in title for term in FOOD_RELEVANT_TERMS)


def detect_law_type(title: str, fallback: str = "고시/훈령") -> str:
    """제목에서 법/시행령/시행규칙/행정예고 중 하나를 판별. 못 찾으면 fallback."""
    if "시행규칙" in title:
        return "시행규칙"
    if "시행령" in title:
        return "시행령"
    if "행정예고" in title or "입법예고" in title or "사전예고" in title:
        return "행정예고"
    if "법률" in title or title.strip().endswith("법"):
        return "법률"
    return fallback


# law.go.kr API(target=law)가 반환하는 공식 법령구분명 → 사용자가 쓰는 관용 명칭으로 정규화
LAWGOKR_TYPE_MAP = {
    "법률": "법률",
    "대통령령": "시행령",
    "총리령": "시행규칙",
    "부령": "시행규칙",
}


def normalize_lawgokr_type(raw_type: str) -> str:
    return LAWGOKR_TYPE_MAP.get(raw_type, raw_type or "법률")
