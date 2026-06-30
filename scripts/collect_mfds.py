"""식약처(MFDS) 법령·고시·훈령 게시판에서 최근 게시물을 수집합니다.

식약처 법령/고시 게시판을 파싱합니다.
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# 식약처 법령·고시·훈령·예규 게시판
BOARD_URL = "https://www.mfds.go.kr/brd/m_228/list.do"
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


def detect_status(title):
    if "행정예고" in title or "입법예고" in title or "사전예고" in title:
        return "예고"
    if "공고" in title:
        return "공고"
    if "개정" in title or "시행" in title:
        return "시행"
    return "공지"


def collect():
    items = []
    cutoff = datetime.today() - timedelta(days=14)  # 최근 2주

    try:
        r = requests.get(BOARD_URL, headers=HEADERS, timeout=15)
        r.raise_for_status()
        r.encoding = "utf-8"

        soup = BeautifulSoup(r.text, "html.parser")
        rows = soup.select("table.board_list tbody tr")

        if not rows:
            # 구조가 다를 경우 대비
            rows = soup.select("tbody tr")

        for row in rows:
            cols = row.select("td")
            if len(cols) < 3:
                continue

            title_el = row.select_one("td a")
            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            if not title:
                continue

            # 날짜는 보통 마지막에서 두 번째 열
            date_text = ""
            for col in reversed(cols):
                text = col.get_text(strip=True)
                if "." in text and len(text) == 10:
                    date_text = text
                    break

            date_obj = parse_date(date_text)
            if date_obj and date_obj < cutoff:
                continue

            href = title_el.get("href", "")
            url = href if href.startswith("http") else "https://www.mfds.go.kr" + href

            items.append({
                "title": title,
                "source": "식약처",
                "status": detect_status(title),
                "date": date_obj.strftime("%Y-%m-%d") if date_obj else date_text,
                "url": url,
                "key_points": [],
                "industry_impact": "",
                "law_type": "고시/훈령",
                "is_new": True,
            })

        print(f"[식약처] {len(items)}건 수집")

    except Exception as e:
        print(f"[식약처] 수집 오류: {e}")

    return items


if __name__ == "__main__":
    result = collect()
    print(f"\n식약처 수집 결과: {len(result)}건")
    for item in result:
        print(f"  - {item['date']} [{item['status']}] {item['title']}")
