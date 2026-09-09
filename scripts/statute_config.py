"""'법령자료' 탭에서 상시 추적하는 법령·행정규칙 목록.

실무자가 항상 참조하는 특정 법령·고시를 API 키워드 검색이 아니라 여기 고정 리스트로
직접 지정한다 (법령 모니터의 키워드 기반 신규 수집과는 성격이 다름). 항목 추가/제외는
이 리스트만 수정하면 된다.

api_target: "law"(법령 조문 API, 조문변경여부 플래그 제공) 또는
            "admrul"(행정규칙/고시 조문 API, 조문번호는 텍스트에서 직접 추출).
query: lawSearch.do에 넘길 검색어 (보통 정식 법령명/행정규칙명과 동일).
text_available: False면 API가 조문 원문 대신 안내 문구만 반환하는 항목
                (예: 방대한 공전류) — 원문 링크만 노출하고 diff 대상에서 제외.
"""

STATUTES = [
    # --- 법령 (target=law) ---
    {"key": "food_label_ad_law", "name": "식품 등의 표시ㆍ광고에 관한 법률",
     "category": "표시광고", "api_target": "law", "query": "식품 등의 표시ㆍ광고에 관한 법률"},
    {"key": "food_label_ad_decree", "name": "식품 등의 표시ㆍ광고에 관한 법률 시행령",
     "category": "표시광고", "api_target": "law", "query": "식품 등의 표시ㆍ광고에 관한 법률 시행령"},
    {"key": "food_label_ad_rule", "name": "식품 등의 표시ㆍ광고에 관한 법률 시행규칙",
     "category": "표시광고", "api_target": "law", "query": "식품 등의 표시ㆍ광고에 관한 법률 시행규칙"},
    {"key": "packaging_rule", "name": "제품의 포장재질ㆍ포장방법에 관한 기준 등에 관한 규칙",
     "category": "포장재", "api_target": "law", "query": "제품의 포장재질ㆍ포장방법에 관한 기준 등에 관한 규칙"},
    {"key": "origin_law", "name": "농수산물의 원산지 표시 등에 관한 법률",
     "category": "원산지", "api_target": "law", "query": "농수산물의 원산지 표시 등에 관한 법률"},
    {"key": "origin_decree", "name": "농수산물의 원산지 표시 등에 관한 법률 시행령",
     "category": "원산지", "api_target": "law", "query": "농수산물의 원산지 표시 등에 관한 법률 시행령"},
    {"key": "origin_rule", "name": "농수산물의 원산지 표시 등에 관한 법률 시행규칙",
     "category": "원산지", "api_target": "law", "query": "농수산물의 원산지 표시 등에 관한 법률 시행규칙"},

    # --- 행정규칙/고시 (target=admrul, 조문 텍스트 diff 가능) ---
    {"key": "hff_label_standard", "name": "건강기능식품의 표시기준",
     "category": "건기식", "api_target": "admrul", "query": "건강기능식품의 표시기준"},
    {"key": "hff_functional_ingredient", "name": "건강기능식품 기능성 원료 및 기준ㆍ규격 인정에 관한 규정",
     "category": "건기식", "api_target": "admrul", "query": "건강기능식품 기능성 원료 및 기준ㆍ규격 인정에 관한 규정"},
    {"key": "food_label_standard", "name": "식품등의 표시기준",
     "category": "표시광고", "api_target": "admrul", "query": "식품등의 표시기준"},
    {"key": "food_additive_standard", "name": "식품첨가물의 기준 및 규격",
     "category": "식품첨가물", "api_target": "admrul", "query": "식품첨가물의 기준 및 규격"},
    {"key": "unfair_ad_functional", "name": "부당한 표시 또는 광고로 보지 아니하는 식품등의 기능성 표시 또는 광고에 관한 규정",
     "category": "표시광고", "api_target": "admrul", "query": "부당한 표시 또는 광고로 보지 아니하는 식품등의 기능성 표시 또는 광고에 관한 규정"},
    {"key": "unfair_ad_content", "name": "식품등의 부당한 표시 또는 광고의 내용 기준",
     "category": "표시광고", "api_target": "admrul", "query": "식품등의 부당한 표시 또는 광고의 내용 기준"},
    {"key": "food_traceability", "name": "식품 등 이력추적관리기준",
     "category": "이력추적", "api_target": "admrul", "query": "식품 등 이력추적관리기준"},
    {"key": "packaging_simple_measure", "name": "제품의 포장재질 및 포장방법에 대한 간이측정방법",
     "category": "포장재", "api_target": "admrul", "query": "제품의 포장재질 및 포장방법에 대한 간이측정방법"},
    {"key": "separate_disposal_mark", "name": "분리배출 표시에 관한 지침",
     "category": "포장재", "api_target": "admrul", "query": "분리배출 표시에 관한 지침"},
    {"key": "packaging_material_grade", "name": "포장재 재질ㆍ구조 등급표시 기준",
     "category": "포장재", "api_target": "admrul", "query": "포장재 재질ㆍ구조 등급표시 기준"},
    {"key": "packaging_recycle_grade", "name": "포장재 재활용 용이성 등급평가 기준",
     "category": "포장재", "api_target": "admrul", "query": "포장재 재활용 용이성 등급평가 기준"},
    {"key": "origin_label_manner", "name": "농수산물의 원산지표시 요령",
     "category": "원산지", "api_target": "admrul", "query": "농수산물의 원산지표시 요령"},

    # --- 행정규칙/고시 (target=admrul) ---
    # "건강기능식품의 기준 및 규격"(공전)은 API가 본문 대신 안내문만 반환 — 원문 링크만 노출됨.
    # 본문 제공 여부는 하드코딩하지 않고 collect_statutes.py가 매 수집 시 실제 응답을 보고
    # 판단한다(같은 유형인 "식품첨가물의 기준 및 규격"도 실측 결과 본문 미제공으로 확인됨).
    {"key": "hff_standard_spec", "name": "건강기능식품의 기준 및 규격",
     "category": "건기식", "api_target": "admrul", "query": "건강기능식품의 기준 및 규격"},
]

STATUTES_BY_KEY = {s["key"]: s for s in STATUTES}

# 조문 개수가 많은 이력을 무한정 쌓지 않도록 법령/고시당 보관할 최대 변경 이력 수
MAX_HISTORY_PER_STATUTE = 20
