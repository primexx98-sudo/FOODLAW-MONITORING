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
import re
import sys
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from urllib.parse import urljoin

sys.path.insert(0, os.path.dirname(__file__))
from law_type_utils import detect_law_type

BODY_TEXT_MAX_CHARS = 3000


def fetch_detail_body(url: str) -> str:
    """상세페이지의 실제 공고 본문("개정이유 및 주요내용", 의견제출 마감 등)을 추출한다.

    지금까지는 목록 페이지의 제목만 가지고 Gemini에게 "개정 내용을 분석해달라"고
    시켰는데, 이러면 모델이 제목만 보고 그럴듯한 내용을 지어낼 수밖에 없다.
    상세페이지 본문(.bv_cont)에는 실제 개정이유·주요내용·의견제출 마감일 등이
    전부 나와 있어서, 이걸 긁어 요약 프롬프트의 근거로 넘기면 훨씬 정확해진다.
    """
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        r.encoding = "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")
        cont = soup.select_one(".bv_cont") or soup.select_one(".bv_contents")
        if not cont:
            return ""
        # <p> 단위로 합쳐야 문단이 유지된다 — get_text(separator="\n")은 <span>마다
        # 줄바꿈을 넣어서 한 문장이 수십 줄로 쪼개짐
        paragraphs = [p.get_text(" ", strip=True) for p in cont.find_all("p")]
        paragraphs = [re.sub(r"\s{2,}", " ", p) for p in paragraphs if p]
        text = "\n".join(paragraphs) if paragraphs else cont.get_text(" ", strip=True)
        return text[:BODY_TEXT_MAX_CHARS]
    except Exception as e:
        print(f"    상세본문 수집 실패 [{url}]: {e}")
        return ""

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


def fetch_list_page(board, page=1):
    """게시판 목록 1페이지 분(보통 10건)을 파싱해 반환. body_text 없이 title/date/url만."""
    url = f"https://www.mfds.go.kr/brd/{board['path']}/list.do"
    r = requests.get(
        url,
        params={"data_stts_gubun": FOOD_CATEGORY, "page": page},
        headers=HEADERS,
        timeout=15,
    )
    r.raise_for_status()
    r.encoding = "utf-8"

    soup = BeautifulSoup(r.text, "html.parser")
    rows = soup.select(".bbs_list01 li")

    parsed = []
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

        href = title_el.get("href", "")
        if not href:
            # 2026-08-19 발견: 극히 드물게 목록 행의 a.title에 href가 비어있는 경우가
            # 있었음 — urljoin(url, "")은 목록 페이지 자기 자신의 URL을 돌려줘서
            # "원문 바로가기"가 실제로는 목록 페이지로 가는 깨진 링크가 되고 있었다.
            # href가 없으면 url을 빈 문자열로 남겨 build_site.py가 버튼을 숨기게 하고,
            # 로그로 남겨 다음에 이 항목의 실제 링크를 수동으로 확인할 수 있게 한다.
            print(f"    [경고] href 없음, 원문 링크 미확보: {title}")
        item_url = urljoin(url, href) if href else ""

        parsed.append({
            "title": title,
            "source": "식약처",
            "status": board["default_status"],
            "date": date_obj.strftime("%Y-%m-%d") if date_obj else date_text,
            "date_obj": date_obj,
            "url": item_url,
            "key_points": [],
            "industry_impact": "",
            "law_type": board["default_law_type"] or detect_law_type(title),
            "is_new": True,
        })
    return parsed


def collect_board(board, cutoff):
    items = []
    try:
        parsed = [it for it in fetch_list_page(board, page=1)
                  if not (it["date_obj"] and it["date_obj"] < cutoff)]

        for it in parsed:
            it.pop("date_obj", None)
            it["body_text"] = fetch_detail_body(it["url"])
            time.sleep(0.3)  # 상세페이지 연속 요청 예의상 딜레이
            items.append(it)

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
