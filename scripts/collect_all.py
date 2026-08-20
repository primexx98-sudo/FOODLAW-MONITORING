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

# 법제처(collect_lawgokr) 연동은 2026-07-22 제외 — LAW_API_KEY가 계속 빈 응답을
# 반환해 원인 파악이 필요했는데, 식약처 자체 게시판(법/시행령/시행규칙 + 입법·행정예고)
# 만으로 충분히 커버된다고 판단해 사용자가 제외 결정. collect_lawgokr.py 파일 자체는
# 남겨둠 — 키 문제가 해결되면 다시 넣을 수 있음.
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

    mfds_items = collect_mfds()
    food_items = collect_foodsafety()

    all_items = deduplicate(mfds_items + food_items)

    week_info = get_week_info()
    archive = load_archive()

    # collect_mfds()는 최근 14일(2주) 창을 스캔하므로, 매주 실행되는 이 스크립트가
    # 지난주에도 이미 수집했던 항목을 이번 주에 또 집어올 수 있다(2026-08-19 발견 —
    # 같은 URL이 인접한 두 주차에 그대로 중복 저장됨). 이번 주차 자신을 제외한 다른
    # 모든 주차에 이미 있는 제목은 걸러내 같은 항목이 두 주차에 겹쳐 쌓이지 않게 한다.
    #
    # 2026-08-20: 키를 url에서 title로 변경 — m_203("법/시행령/시행규칙") 게시판의
    # 항목들은 MFDS 자체 상세페이지가 아니라 law.go.kr의 "현행 법령 조회" 링크를
    # 그대로 가리키는데, 이 링크는 법령명 기준 고정 URL이라 같은 법이 여러 차례
    # 개정될 때마다 서로 다른 개정공포(예: 2023년 총리령 제1868호 vs 2026년 총리령
    # 제2141호)가 전부 같은 URL을 공유한다. url 기준 dedup은 이런 경우 최신 개정을
    # "이미 수집된 항목"으로 오판해 통째로 누락시켰음(실제 사례: 축산물 위생관리법
    # 시행규칙/시행령 2026-08-11 개정 공포 알림 누락). title은 개정 번호·날짜가
    # 포함돼 있어 서로 다른 개정을 안전하게 구분한다.
    other_week_titles = {
        it.get("title", "").strip()
        for w in archive["weeks"]
        if not (w.get("year") == week_info["year"] and w.get("week_num") == week_info["week_num"])
        for it in w.get("items", [])
        if it.get("title")
    }
    before_cross_dedup = len(all_items)
    all_items = [it for it in all_items if it.get("title", "").strip() not in other_week_titles]
    if before_cross_dedup != len(all_items):
        print(f"다른 주차와 중복된 {before_cross_dedup - len(all_items)}건 제외")

    # 날짜 최신순 정렬
    all_items.sort(key=lambda x: x.get("date", ""), reverse=True)

    print(f"\n총 {len(all_items)}건 (중복 제거 후)")

    n_mfds = sum(1 for i in all_items if i.get("source") == "식약처")
    n_food = sum(1 for i in all_items if i.get("source") == "식품안전나라")
    week_entry = {
        **week_info,
        "summary": (
            f"{week_info['start_date']} ~ {week_info['end_date']} 기간 "
            f"식품 법령 개정 {len(all_items)}건 수집. "
            f"식약처 {n_mfds}건 · 식품안전나라 {n_food}건."
        ),
        "items": all_items,
        "collected_at": datetime.now().isoformat(),
        "counts": {
            "total": len(all_items),
            "식약처": n_mfds,
            "식품안전나라": n_food,
            "시행": sum(1 for i in all_items if i.get("status") == "시행"),
            "예고": sum(1 for i in all_items if i.get("status") == "예고"),
        },
    }

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
