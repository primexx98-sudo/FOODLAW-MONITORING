"""식약처 게시판(m_203, m_209)을 2023-01-01까지 페이지네이션으로 거슬러 올라가며
과거 데이터를 수집하는 1회성 스크립트.

collect_mfds.py는 최근 14일치만 다루므로, 2023~2026년 전체 백데이터가 필요하면
이 스크립트로 한 번 백필한다. 각 게시판은 ?page=N 파라미터로 과거 페이지 조회 가능
(10건/페이지). 실측 결과 2023-01-01 이후 데이터는 m_203 약 1~6페이지,
m_209 약 1~19페이지에 걸쳐 있음(2026-07-23 확인).

실행:
  python scripts/collect_historical_mfds.py
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))
from collect_mfds import BOARDS, fetch_list_page, fetch_detail_body

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
ARCHIVE_PATH = os.path.join(REPO_ROOT, "data", "archive.json")

FLOOR_DATE = datetime(2023, 1, 1)
MAX_PAGES = 40  # 안전장치 — 예상보다 페이지가 많아도 무한루프 방지


def collect_board_historical(board):
    items = []
    page = 1
    while page <= MAX_PAGES:
        parsed = fetch_list_page(board, page=page)
        if not parsed:
            print(f"[{board['path']}] page {page}: 더 이상 항목 없음, 종료")
            break

        in_range = [it for it in parsed if it["date_obj"] and it["date_obj"] >= FLOOR_DATE]
        items.extend(in_range)
        oldest_on_page = min((it["date_obj"] for it in parsed if it["date_obj"]), default=None)
        print(f"[{board['path']}] page {page}: {len(parsed)}건 중 {len(in_range)}건 범위 내 (페이지 최고령 {oldest_on_page})")

        if oldest_on_page and oldest_on_page < FLOOR_DATE:
            break
        page += 1
        time.sleep(0.3)

    for it in items:
        it.pop("date_obj", None)
        it["body_text"] = fetch_detail_body(it["url"])
        time.sleep(0.3)

    return items


def deduplicate(items):
    seen = set()
    result = []
    for item in items:
        key = item["title"].strip()
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def week_key(date_str):
    d = datetime.strptime(date_str, "%Y-%m-%d")
    year, week_num, _ = d.isocalendar()
    return year, week_num


def load_archive():
    if os.path.exists(ARCHIVE_PATH):
        with open(ARCHIVE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"weeks": [], "total_weeks": 0}


def main():
    all_items = []
    for board in BOARDS:
        print(f"\n=== {board['path']} 과거 데이터 수집 시작 ===")
        all_items.extend(collect_board_historical(board))

    all_items = deduplicate(all_items)
    print(f"\n총 {len(all_items)}건 수집 (중복 제거 후)")

    archive = load_archive()
    existing_titles = {it["title"].strip() for w in archive["weeks"] for it in w.get("items", [])}
    new_items = [it for it in all_items if it["title"].strip() not in existing_titles]
    print(f"기존 아카이브에 없는 신규 항목: {len(new_items)}건")

    buckets = {}
    for it in new_items:
        wk = week_key(it["date"])
        buckets.setdefault(wk, []).append(it)

    for (year, week_num), items in buckets.items():
        items.sort(key=lambda x: x["date"], reverse=True)
        d = datetime.strptime(items[0]["date"], "%Y-%m-%d")
        start = d - timedelta(days=d.weekday())
        end = start + timedelta(days=6)

        match = next(
            (w for w in archive["weeks"] if w.get("year") == year and w.get("week_num") == week_num),
            None,
        )
        week_entry = {
            "year": year,
            "week_num": week_num,
            "start_date": start.strftime("%Y-%m-%d"),
            "end_date": end.strftime("%Y-%m-%d"),
            "label": f"{year}년 {week_num}주차",
            "summary": f"식약처 식품 법령 개정 {len(items)}건 (과거 백필)",
            "items": items,
            "collected_at": datetime.now().isoformat(),
            "counts": {
                "total": len(items),
                "식약처": len(items),
                "식품안전나라": 0,
                "시행": sum(1 for i in items if i.get("status") == "시행"),
                "예고": sum(1 for i in items if i.get("status") == "예고"),
            },
        }
        if match:
            match["items"].extend(items)
            match["items"].sort(key=lambda x: x["date"], reverse=True)
            match["counts"]["total"] = len(match["items"])
            match["counts"]["식약처"] = match["counts"].get("식약처", 0) + len(items)
        else:
            archive["weeks"].append(week_entry)

    archive["weeks"].sort(key=lambda w: (w.get("year", 0), w.get("week_num", 0)))
    archive["total_weeks"] = len(archive["weeks"])
    archive["last_updated"] = datetime.now().isoformat()

    with open(ARCHIVE_PATH, "w", encoding="utf-8") as f:
        json.dump(archive, f, ensure_ascii=False, indent=2)

    print(f"\n완료: {len(new_items)}건 추가, 총 {archive['total_weeks']}주차 누적")
    print("다음 단계: python scripts/summarize_items.py (최근 항목부터 순차 요약)")


if __name__ == "__main__":
    main()
