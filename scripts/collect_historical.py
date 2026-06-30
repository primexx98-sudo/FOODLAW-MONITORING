"""2026년 1주차부터 현재까지 전체 주간 데이터를 한 번에 수집합니다.

Playwright 기반 (식약처 JS 렌더링 대응).
실행:
  python scripts/collect_historical.py
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
ARCHIVE_PATH = os.path.join(REPO_ROOT, "data", "archive.json")

FOOD_KEYWORDS = [
    "식품", "건강기능식품", "축산물", "식품위생", "식품안전",
    "건기식", "식품첨가물", "식품표시", "기능성원료", "품목제조",
]

CUTOFF = datetime(2026, 1, 1)


def is_food_related(title: str) -> bool:
    return any(kw in title for kw in FOOD_KEYWORDS)


def clean_title(title: str) -> str:
    return title.replace("새로운게시물", "").replace("NEW", "").strip()


def parse_board_text(body_text: str, source_label: str, default_status: str):
    """식약처 게시판 inner_text 파싱.

    구조:
      2151\t식품의 기준 및 규격 일부개정고시(안) 행정예고(...) 새로운게시물
      담당부서 | 식품기준과
      조회수 | 608
      [첨부파일 라인들...]
      2026-06-30          <- 날짜 (다음 항목 번호 직전)
    """
    items = []
    lines = [l.strip() for l in body_text.split("\n") if l.strip()]
    total = len(lines)

    # 항목 번호가 있는 라인 수집
    item_indices = []
    for idx, line in enumerate(lines):
        m = re.match(r"^(\d{1,4})\t(.+)$", line)
        if m:
            item_indices.append((idx, int(m.group(1)), m.group(2).strip()))

    for k, (idx, num, raw_title) in enumerate(item_indices):
        title = clean_title(raw_title)
        if not is_food_related(title):
            continue

        # 날짜는 이 항목~다음 항목 사이 (최대 20줄)
        next_idx = item_indices[k + 1][0] if k + 1 < len(item_indices) else total
        date_str = ""
        for j in range(idx + 1, min(next_idx, idx + 20)):
            date_m = re.search(r"(\d{4}-\d{2}-\d{2})", lines[j])
            if date_m:
                date_str = date_m.group(1)  # 마지막 날짜 사용

        if not date_str:
            continue

        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            continue

        if date_obj < CUTOFF:
            return items, True

        status = default_status
        if "행정예고" in title or "입법예고" in title or "예고" in title:
            status = "예고"
        elif "시행" in title or "개정" in title:
            status = "시행"
        elif "공고" in title:
            status = "공고"

        items.append({
            "title": title,
            "source": "식약처",
            "status": status,
            "date": date_str,
            "url": f"https://www.mfds.go.kr/brd/{source_label.split('?')[0]}/list.do",
            "key_points": [],
            "industry_impact": "",
            "law_type": "고시/훈령" if "m_203" in source_label else "행정예고",
            "is_new": False,
        })

    return items, False


def scrape_mfds_board(page, board_id: str, board_name: str, default_status: str, max_pages: int = 30):
    """식약처 게시판 페이지를 순회하며 2026년 데이터 수집."""
    all_items = []

    if "?" in board_id:
        bid, qs = board_id.split("?", 1)
        base_url = f"https://www.mfds.go.kr/brd/{bid}/list.do?{qs}"
    else:
        base_url = f"https://www.mfds.go.kr/brd/{board_id}/list.do?"

    for page_num in range(1, max_pages + 1):
        try:
            url = f"{base_url}&page={page_num}"
            page.goto(url, timeout=20000)
            page.wait_for_load_state("networkidle", timeout=15000)

            body = page.inner_text("body")
            items, reached_cutoff = parse_board_text(body, board_id, default_status)
            all_items.extend(items)

            print(f"  [{board_name}] p{page_num}: {len(items)}건 (누적: {len(all_items)})")

            if reached_cutoff:
                print(f"  [{board_name}] 2026년 이전 도달, 중단")
                break

            time.sleep(0.8)

        except Exception as e:
            print(f"  [{board_name}] p{page_num} 오류: {e}")
            break

    return all_items


def scrape_lawgokr(page, max_pages: int = 5):
    """법제처 법령 검색 결과에서 2026년 식품 법령 수집."""
    all_items = []
    keywords = ["건강기능식품", "식품위생법", "식품안전기본법", "축산물 위생관리법"]

    for keyword in keywords:
        print(f"  [법제처] '{keyword}' 검색 중...")
        try:
            page.goto(
                f"https://www.law.go.kr/lsSc.do?menuId=1&subMenuId=15&tabMenuId=81"
                f"&eventGubun=060101&query={keyword}&x=0&y=0",
                timeout=20000,
            )
            page.wait_for_load_state("networkidle", timeout=15000)

            body = page.inner_text("body")
            lines = [l.strip() for l in body.split("\n") if l.strip()]

            for i, line in enumerate(lines):
                date_m = re.search(r"(\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.?)", line)
                if not date_m:
                    continue

                raw_date = re.sub(r"\s+", "", date_m.group(1)).rstrip(".")
                parts = raw_date.split(".")
                if len(parts) < 3:
                    continue
                try:
                    date_obj = datetime(int(parts[0]), int(parts[1]), int(parts[2]))
                except (ValueError, IndexError):
                    continue

                if date_obj < CUTOFF or date_obj > datetime.today():
                    continue

                title = lines[i - 1].strip() if i > 0 else line
                if len(title) < 5 or not is_food_related(title):
                    continue

                all_items.append({
                    "title": title,
                    "source": "법제처",
                    "status": "시행",
                    "date": date_obj.strftime("%Y-%m-%d"),
                    "url": f"https://www.law.go.kr/lsSc.do?query={keyword}",
                    "key_points": [],
                    "industry_impact": "",
                    "law_type": "법령",
                    "is_new": False,
                })

            print(f"  [법제처] '{keyword}' -> {len(all_items)}건 누적")
            time.sleep(1)

        except Exception as e:
            print(f"  [법제처] '{keyword}' 오류: {e}")

    seen = set()
    return [x for x in all_items if x["title"] not in seen and not seen.add(x["title"])]


def generate_weeks(start: datetime, end: datetime):
    current = start - timedelta(days=start.weekday())
    weeks = []
    while current <= end:
        week_end = current + timedelta(days=6)
        year, wnum, _ = current.isocalendar()
        weeks.append({
            "year": year,
            "week_num": wnum,
            "start": current,
            "end": min(week_end, end),
            "start_str": current.strftime("%Y-%m-%d"),
            "end_str": min(week_end, end).strftime("%Y-%m-%d"),
            "label": f"{year}년 {wnum}주차",
        })
        current += timedelta(days=7)
    return weeks


def assign_to_weeks(items, weeks):
    week_map = {w["week_num"]: [] for w in weeks}
    for item in items:
        try:
            d = datetime.strptime(item["date"][:10], "%Y-%m-%d")
        except ValueError:
            continue
        year, wnum, _ = d.isocalendar()
        if year == 2026 and wnum in week_map:
            week_map[wnum].append(item)
    return week_map


def build_archive(weeks, week_map):
    entries = []
    for w in reversed(weeks):
        items = sorted(week_map.get(w["week_num"], []), key=lambda x: x.get("date", ""), reverse=True)
        if w == weeks[-1]:
            for it in items:
                it["is_new"] = True

        enforce = sum(1 for i in items if i.get("status") == "시행")
        notice = sum(1 for i in items if i.get("status") == "예고")

        entries.append({
            "year": w["year"],
            "week_num": w["week_num"],
            "start_date": w["start_str"],
            "end_date": w["end_str"],
            "label": w["label"],
            "summary": (
                f"{w['start_str']} ~ {w['end_str']} 식품 법령 {len(items)}건. "
                f"시행 {enforce}건 / 예고 {notice}건."
            ) if items else f"{w['start_str']} ~ {w['end_str']} 수집 항목 없음.",
            "counts": {
                "total": len(items),
                "법제처": sum(1 for i in items if i.get("source") == "법제처"),
                "식약처": sum(1 for i in items if i.get("source") == "식약처"),
                "식품안전나라": sum(1 for i in items if i.get("source") == "식품안전나라"),
                "시행": enforce,
                "예고": notice,
            },
            "items": items,
            "collected_at": datetime.now().isoformat(),
        })

    entries.reverse()
    return {
        "weeks": entries,
        "total_weeks": len(entries),
        "last_updated": datetime.now().isoformat(),
    }


def main():
    print("=" * 60)
    print("2026년 전체 주간 식품 법령 데이터 수집 (Playwright)")
    print("=" * 60)

    start = datetime(2026, 1, 5)
    end = datetime.today()
    weeks = generate_weeks(start, end)
    print(f"수집 범위: {weeks[0]['label']} ~ {weeks[-1]['label']} ({len(weeks)}주)")

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = ctx.new_page()

        print("\n[식약처] 고시 게시판 수집 중...")
        mfds_gosi = scrape_mfds_board(page, "m_203", "식약처 고시", "시행", max_pages=15)

        print("\n[식약처] 행정예고 게시판 (식품) 수집 중...")
        mfds_notice = scrape_mfds_board(
            page, "m_209?data_stts_gubun=C1002", "식약처 행정예고", "예고", max_pages=30
        )

        print("\n[법제처] 법령 검색 수집 중...")
        law_items = scrape_lawgokr(page)

        browser.close()

    all_items = mfds_gosi + mfds_notice + law_items
    seen = set()
    unique = []
    for item in all_items:
        key = item["title"].strip()
        if key not in seen:
            seen.add(key)
            unique.append(item)

    print(f"\n전체: {len(all_items)}건 -> 중복 제거 후 {len(unique)}건")
    print(f"  식약처 고시: {len(mfds_gosi)}건")
    print(f"  식약처 행정예고: {len(mfds_notice)}건")
    print(f"  법제처: {len(law_items)}건")

    week_map = assign_to_weeks(unique, weeks)
    archive = build_archive(weeks, week_map)

    os.makedirs(os.path.dirname(ARCHIVE_PATH), exist_ok=True)
    with open(ARCHIVE_PATH, "w", encoding="utf-8") as f:
        json.dump(archive, f, ensure_ascii=False, indent=2)

    print(f"\n아카이브 저장: {ARCHIVE_PATH}")

    # 주차별 요약 (Windows 인코딩 안전 출력)
    print("\n[주차별 현황]")
    for w in archive["weeks"]:
        cnt = w["counts"]["total"]
        bar = "*" * min(cnt, 25)
        label = w["label"].encode("cp949", "replace").decode("cp949")
        print(f"  {label:14s} {cnt:3d}건 {bar}")

    print(f"\n총 {archive['total_weeks']}주차 / {len(unique)}건 완료")


if __name__ == "__main__":
    main()
