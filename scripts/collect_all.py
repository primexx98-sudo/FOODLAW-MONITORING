"""모든 출처에서 법령 데이터를 수집하고 data/archive.json을 업데이트합니다.

실행 방법:
  python scripts/collect_all.py
"""

import json
import os
import sys
from datetime import datetime, timedelta

# 스크립트 폴더를 경로에 추가 (sibling 모듈 import용)
sys.path.insert(0, os.path.dirname(__file__))

from collect_lawgokr import collect as collect_law
from collect_mfds import collect as collect_mfds
from collect_foodsafety import collect as collect_foodsafety

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
ARCHIVE_PATH = os.path.join(REPO_ROOT, "data", "archive.json")


def get_week_info():
    today = datetime.today()
    start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=6)
    year, week_num, _ = today.isocalendar()
    return {
        "year": year,
        "week_num": week_num,
        "start_date": start.strftime("%Y-%m-%d"),
        "end_date": end.strftime("%Y-%m-%d"),
        "label": f"{year}년 {week_num}주차",
    }


def load_archive():
    if os.path.exists(ARCHIVE_PATH):
        with open(ARCHIVE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"weeks": [], "total_weeks": 0}


def save_archive(data):
    os.makedirs(os.path.dirname(ARCHIVE_PATH), exist_ok=True)
    with open(ARCHIVE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def deduplicate(items):
    seen = set()
    result = []
    for item in items:
        key = item["title"].strip()
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def main():
    print("=" * 50)
    print("식품 법령 수집 시작:", datetime.now().strftime("%Y-%m-%d %H:%M"))
    print("=" * 50)

    law_items = collect_law()
    mfds_items = collect_mfds()
    food_items = collect_foodsafety()

    all_items = deduplicate(law_items + mfds_items + food_items)
    # 날짜 최신순 정렬
    all_items.sort(key=lambda x: x.get("date", ""), reverse=True)

    print(f"\n총 {len(all_items)}건 (중복 제거 후)")

    week_info = get_week_info()
    week_entry = {
        **week_info,
        "summary": (
            f"{week_info['start_date']} ~ {week_info['end_date']} 기간 "
            f"식품 법령 개정 {len(all_items)}건 수집. "
            f"법제처 {len(law_items)}건 · 식약처 {len(mfds_items)}건 · "
            f"식품안전나라 {len(food_items)}건."
        ),
        "items": all_items,
        "collected_at": datetime.now().isoformat(),
        "counts": {
            "total": len(all_items),
            "법제처": len(law_items),
            "식약처": len(mfds_items),
            "식품안전나라": len(food_items),
            "시행": sum(1 for i in all_items if i.get("status") == "시행"),
            "예고": sum(1 for i in all_items if i.get("status") == "예고"),
        },
    }

    archive = load_archive()

    # 같은 연도+주차가 이미 있으면 교체, 없으면 추가
    match = next(
        (w for w in archive["weeks"]
         if w.get("year") == week_info["year"] and w.get("week_num") == week_info["week_num"]),
        None,
    )
    if match:
        idx = archive["weeks"].index(match)
        archive["weeks"][idx] = week_entry
        print("기존 주차 항목 업데이트")
    else:
        archive["weeks"].append(week_entry)
        print("새 주차 항목 추가")

    # 저장은 항상 연도+주차 오름차순 (과거 → 최신) 유지
    archive["weeks"].sort(key=lambda w: (w.get("year", 0), w.get("week_num", 0)))
    archive["total_weeks"] = len(archive["weeks"])
    archive["last_updated"] = datetime.now().isoformat()

    save_archive(archive)
    print(f"\n아카이브 저장 완료: {ARCHIVE_PATH}")
    print(f"총 {archive['total_weeks']}주차 누적")


if __name__ == "__main__":
    main()
