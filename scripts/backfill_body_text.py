"""기존 archive.json 항목 중 body_text가 없는 것들에 상세페이지 본문을 채워 넣는 1회성 스크립트.

2026-07-23 이전에 수집된 항목은 목록 페이지의 제목만 저장하고 있어서, 상세페이지의
실제 개정이유·주요내용을 담은 body_text가 없다. 이 스크립트로 한 번 백필해두면
다음 summarize_items.py 실행 때 근거 있는 요약으로 자동 재생성된다(needs_update 참고).

실행:
  python scripts/backfill_body_text.py
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from collect_mfds import fetch_detail_body

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
ARCHIVE_PATH = os.path.join(REPO_ROOT, "data", "archive.json")


def main():
    with open(ARCHIVE_PATH, encoding="utf-8") as f:
        archive = json.load(f)

    targets = [
        it
        for w in archive["weeks"]
        for it in w.get("items", [])
        if it.get("url") and not it.get("body_text")
    ]
    print(f"백필 대상 {len(targets)}건")

    filled = 0
    for it in targets:
        title = it.get("title", "")[:40]
        print(f"  {title}... ", end="", flush=True)
        body = fetch_detail_body(it["url"])
        it["body_text"] = body
        if body:
            filled += 1
            print(f"완료 ({len(body)}자)")
        else:
            print("실패/빈 본문")
        time.sleep(0.3)

    with open(ARCHIVE_PATH, "w", encoding="utf-8") as f:
        json.dump(archive, f, ensure_ascii=False, indent=2)

    print(f"\n완료: {filled}/{len(targets)}건 본문 확보, archive.json 저장")
    print("다음 단계: python scripts/summarize_items.py (근거 있는 요약으로 재생성됨)")


if __name__ == "__main__":
    main()
