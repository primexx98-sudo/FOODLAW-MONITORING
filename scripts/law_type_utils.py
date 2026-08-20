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

# MFDS 공고 제목은 거의 항상 발신 기관명("...식품의약품안전처공고 제OOOO호")을 인용하는데,
# 이 기관명 자체에 "의약품"이 부분 문자열로 들어있어 FOOD_EXCLUDE_TERMS의 "의약품"이 오탐된다
# (2026-08-20 발견: 「식품 등의 표시·광고에 관한 법률 시행규칙」 개정안 — 참깨/들깨/아몬드/
# 캐슈너트 알레르기 표시대상 추가 — 가 이 오탐으로 통째로 걸러진 채 누락되고 있었음).
# 판별 전에 기관명 자기인용만 제거해 진짜 "의약품"(의약품 관련 규정) 키워드와 구분한다.
AGENCY_NAME = "식품의약품안전처"


def is_food_related(title: str) -> bool:
    normalized = title.replace(AGENCY_NAME, "")
    if any(term in normalized for term in FOOD_EXCLUDE_TERMS):
        return False
    return any(term in normalized for term in FOOD_RELEVANT_TERMS)


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
