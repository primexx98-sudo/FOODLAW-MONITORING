"""식약처(MFDS) 법령 게시판에서 최근 게시물을 수집합니다.

2026-07-22 재작성: 기존 BOARD_URL(m_228)은 실제로 "교육홍보물" 게시판이라 법령과
무관한 내용을 긁어오고 있었음(구조 변경이 아니라 애초에 잘못된 게시판 번호였음).
실제 법령 게시판은 아래 두 곳:
  - m_203 "법, 시행령, 시행규칙" — 이미 공포된 법령
  - m_209 "입법/행정예고" — 시행 전 예고 단계
각 게시판은 ?data_stts_gubun=C1002 파라미터로 "식품" 분야만 서버사이드 필터링 가능
(다른 코드: C1001 공통, C1003 의약품, C1004 의료기기, C1006 화장품 등 — MFDS는
식품 외에도 이 분야들을 같은 게시판에서 다루므로 이 필터가 없으면 전혀 무관한
항목이 섞여 들어온다).
"""

import os
import sys
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from urllib.parse import urljoin

sys.path.insert(0, os.path.dirname(__file__))
from law_type_utils import detect_law_type

BOARDS = [
    {"path": "m_203", "default_status": "시행", "default_law_type": None},
    {"path": "m_209", "default_status": "예고", "default_law_type": "행정예고"},
]
FOOD_CATEGORY = "C1002"  # 분야별선택: 식품
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def parse_date(text):
    """'2026.06.02' 또는 '2026-06-02' → datetime"""
    text = text.strip().replace(".", "-")
    try:
        return datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        return None


def collect_board(board, cutoff):
    items = []
    url = f"https://www.mfds.go.kr/brd/{board['path']}/list.do"
    try:
        r = requests.get(url, params={"data_stts_gubun": FOOD_CATEGORY}, headers=HEADERS, timeout=15)
        r.raise_for_status()
        r.encoding = "utf-8"

        soup = BeautifulSoup(r.text, "html.parser")
        rows = soup.select(".bbs_list01 li")

        for row in rows:
            title_el = row.select_one("a.title")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            if not title:
                continue

            date_el = row.select_one(".right_column")
            date_text = date_el.get_text(strip=True) if date_el else ""
            date_obj = parse_date(date_text)
            if date_obj and date_obj < cutoff:
                continue

            href = title_el.get("href", "")
            item_url = urljoin(url, href)

            items.append({
                "title": title,
                "source": "식약처",
                "status": board["default_status"],
                "date": date_obj.strftime("%Y-%m-%d") if date_obj else date_text,
                "url": item_url,
                "key_points": [],
                "industry_impact": "",
                "law_type": board["default_law_type"] or detect_law_type(title),
                "is_new": True,
            })

        print(f"[식약처:{board['path']}] {len(items)}건 수집")

    except Exception as e:
        print(f"[식약처:{board['path']}] 수집 오류: {e}")

    return items


def collect():
    cutoff = datetime.today() - timedelta(days=14)  # 최근 2주
    items = []
    for board in BOARDS:
        items.extend(collect_board(board, cutoff))
    return items


if __name__ == "__main__":
    result = collect()
    print(f"\n식약처 수집 결과: {len(result)}건")
    for item in result:
        print(f"  - {item['date']} [{item['status']}/{item['law_type']}] {item['title']}")
