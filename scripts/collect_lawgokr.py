"""법제처 국가법령정보 OpenAPI에서 식품 관련 법령 개정 정보를 수집합니다.

API 키는 환경변수 LAW_API_KEY 에서 읽습니다.
국가법령정보 공동활용: https://open.law.go.kr
"""

import os
import sys
import requests
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))
from law_type_utils import normalize_lawgokr_type

API_KEY = os.environ.get("LAW_API_KEY", "")
BASE_URL = "https://www.law.go.kr/DRF/lawSearch.do"

FOOD_KEYWORDS = ["식품위생", "건강기능식품", "식품안전", "식품표시", "축산물위생"]


def get_date_range():
    today = datetime.today()
    start = today - timedelta(days=today.weekday() + 7)  # 지난 주 월요일
    end = today
    return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")


def search_laws(keyword, page=1):
    params = {
        "OC": API_KEY,
        "target": "law",
        "type": "JSON",
        "query": keyword,
        "display": 20,
        "page": page,
        "sort": "date",
    }
    r = requests.get(BASE_URL, params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def format_date(raw):
    """'20260602' → '2026-06-02'"""
    if len(raw) == 8:
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"
    return raw


def collect():
    if not API_KEY:
        print("[법제처] LAW_API_KEY 환경변수가 설정되지 않았습니다. 건너뜁니다.")
        return []

    start_date, end_date = get_date_range()
    items = []
    seen_ids = set()

    for keyword in FOOD_KEYWORDS:
        try:
            data = search_laws(keyword)
            law_search = data.get("LawSearch", {})
            laws = law_search.get("law", [])
            if isinstance(laws, dict):
                laws = [laws]

            for law in laws:
                law_id = law.get("법령ID", "")
                if law_id in seen_ids:
                    continue
                seen_ids.add(law_id)

                prom_dt = law.get("공포일자", "")
                if not prom_dt or prom_dt < start_date:
                    continue

                name = law.get("법령명한글", "")
                # law.go.kr API의 공식 법령구분명(대통령령/부령 등)을 법/시행령/시행규칙/행정예고
                # 관용 명칭으로 정규화 — law_type_utils.py 참고
                law_type = normalize_lawgokr_type(law.get("법령구분명", ""))

                # 상태 분류
                if "예고" in name:
                    status = "예고"
                    law_type = "행정예고"
                elif "시행" in name or law.get("시행일자", ""):
                    status = "시행"
                else:
                    status = "공포"

                items.append({
                    "title": name,
                    "source": "법제처",
                    "status": status,
                    "date": format_date(prom_dt),
                    "url": f"https://www.law.go.kr/법령/{name}",
                    "key_points": [],
                    "industry_impact": "",
                    "law_type": law_type,
                    "is_new": True,
                })

            print(f"[법제처] '{keyword}' → {len(laws)}건")

        except Exception as e:
            print(f"[법제처] '{keyword}' 수집 오류: {e}")

    return items


if __name__ == "__main__":
    result = collect()
    print(f"\n법제처 수집 결과: {len(result)}건")
    for item in result:
        print(f"  - {item['date']} [{item['status']}] {item['title']}")
