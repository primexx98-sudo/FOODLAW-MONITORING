"""식품안전나라 공지사항·법령정보에서 최근 게시물을 수집합니다."""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

BOARD_URL = (
    "https://www.foodsafetykorea.go.kr/portal/board/boardList.do"
    "?menu_no=2815&menu_grp=MENU_NEW02"
)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def parse_date(text):
    text = text.strip().replace(".", "-")
    try:
        return datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        return None


def detect_status(title):
    if "예고" in title or "입법" in title:
        return "예고"
    if "개정" in title or "시행" in title:
        return "시행"
    return "공지"


def collect():
    items = []
    cutoff = datetime.today() - timedelta(days=14)

    try:
        r = requests.get(BOARD_URL, headers=HEADERS, timeout=15)
        r.raise_for_status()
        r.encoding = "utf-8"

        soup = BeautifulSoup(r.text, "html.parser")
        rows = soup.select("table tbody tr")

        for row in rows:
            title_el = row.select_one("td a")
            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            if not title:
                continue

            cols = row.select("td")
            date_text = ""
            for col in reversed(cols):
                text = col.get_text(strip=True)
                if "-" in text and len(text) == 10:
                    date_text = text
                    break
                if "." in text and len(text) == 10:
                    date_text = text
                    break

            date_obj = parse_date(date_text)
            if date_obj and date_obj < cutoff:
                continue

            href = title_el.get("href", "")
            if href.startswith("http"):
                url = href
            elif href.startswith("/"):
                url = "https://www.foodsafetykorea.go.kr" + href
            else:
                url = "https://www.foodsafetykorea.go.kr/portal/board/" + href

            items.append({
                "title": title,
                "source": "식품안전나라",
                "status": detect_status(title),
                "date": date_obj.strftime("%Y-%m-%d") if date_obj else date_text,
                "url": url,
                "key_points": [],
                "industry_impact": "",
                "law_type": "공지사항",
                "is_new": True,
            })

        print(f"[식품안전나라] {len(items)}건 수집")

    except Exception as e:
        print(f"[식품안전나라] 수집 오류: {e}")

    return items


if __name__ == "__main__":
    result = collect()
    print(f"\n식품안전나라 수집 결과: {len(result)}건")
    for item in result:
        print(f"  - {item['date']} [{item['status']}] {item['title']}")
