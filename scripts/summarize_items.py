"""Claude API를 사용해 archive.json 각 항목의 핵심 내용·업계 영향·주간 요약을 생성합니다.

실행:
  $env:ANTHROPIC_API_KEY="sk-ant-..."
  python scripts/summarize_items.py
"""

import json
import os
import sys
import time

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
ARCHIVE_PATH = os.path.join(REPO_ROOT, "data", "archive.json")

MODEL = "claude-haiku-4-5-20251001"


def call_claude(client, prompt: str) -> str:
    resp = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text.strip()


def summarize_item(client, item: dict) -> dict:
    title = item.get("title", "")
    source = item.get("source", "")
    status = item.get("status", "")
    date = item.get("date", "")
    law_type = item.get("law_type", "")

    prompt = f"""당신은 식품산업 법령 전문 분석가입니다.
아래 식품 법령 개정 정보를 분석해 JSON으로 반환하세요.

제목: {title}
출처: {source}
상태: {status} ({law_type})
날짜: {date}

다음 형식으로만 반환 (다른 텍스트 없이 JSON만):
{{
  "key_points": [
    "① [변경 내용 핵심 1] — [간단 설명]",
    "② [변경 내용 핵심 2] — [간단 설명]",
    "③ [변경 내용 핵심 3] — [간단 설명]"
  ],
  "industry_impact": "식품 업계에 미치는 영향을 1~2문장으로 설명",
  "related_laws": [
    {{"title": "관련 법령명 1", "url": "https://www.law.go.kr/법령/법령명"}},
    {{"title": "관련 법령명 2", "url": "https://www.law.go.kr/법령/법령명"}}
  ]
}}

조건:
- key_points는 제목에서 유추 가능한 구체적 변경 사항 3개 (없으면 2개)
- industry_impact는 식품 제조·판매·수입 업체 관점에서 실질적 영향
- related_laws는 제목에서 유추된 관련 법령 1~3개, URL은 법제처 또는 식약처
- 한국어로만 작성"""

    try:
        text = call_claude(client, prompt)
        # JSON 블록 추출
        text = text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        return json.loads(text)
    except Exception as e:
        print(f"    파싱 오류 ({e}): {text[:100] if 'text' in dir() else 'N/A'}")
        return {
            "key_points": [],
            "industry_impact": "",
            "related_laws": [],
        }


def summarize_week(client, week: dict) -> str:
    items = week.get("items", [])
    if not items:
        return ""

    items_text = "\n".join(
        f"- [{it.get('status', '')}] {it.get('title', '')} ({it.get('date', '')})"
        for it in items
    )
    label = week.get("label", "")
    start = week.get("start_date", "")
    end = week.get("end_date", "")

    prompt = f"""당신은 식품산업 법령 분석가입니다.
{label} ({start}~{end}) 식품 법령 변동 내역을 바탕으로 업계 담당자를 위한 통합 요약문을 작성하세요.

이번 주 변동 항목:
{items_text}

조건:
- 3~5문장의 한국어 단락
- "이번 주 가장 주목할 사항은..." 으로 시작
- 시행 중인 사항과 예고된 사항을 구분해 설명
- 실무 담당자가 즉시 확인해야 할 내용 강조
- 다음 주 예상 발령 가능성이 있는 항목 언급 (있을 경우)"""

    try:
        return call_claude(client, prompt)
    except Exception as e:
        print(f"    주간 요약 오류: {e}")
        return ""


def needs_update(item: dict) -> bool:
    return not item.get("key_points") or len(item.get("key_points", [])) == 0


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("[경고] ANTHROPIC_API_KEY 환경변수가 설정되지 않아 요약 단계를 건너뜁니다.")
        print("  PowerShell: $env:ANTHROPIC_API_KEY='sk-ant-...'")
        print("  GitHub Actions: Settings → Secrets → ANTHROPIC_API_KEY 등록")
        return

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
    except ImportError:
        print("[오류] anthropic 패키지가 없습니다: pip install anthropic")
        sys.exit(1)

    with open(ARCHIVE_PATH, encoding="utf-8") as f:
        archive = json.load(f)

    total_items = sum(len(w.get("items", [])) for w in archive["weeks"])
    needs = sum(
        sum(1 for it in w.get("items", []) if needs_update(it))
        for w in archive["weeks"]
    )
    print(f"전체 {total_items}건 중 요약 필요 {needs}건")

    updated = 0
    for week in archive["weeks"]:
        items = week.get("items", [])
        if not items:
            continue

        label = week.get("label", "")
        week_updated = False

        for i, item in enumerate(items):
            if not needs_update(item):
                continue

            title = item.get("title", "")[:40]
            print(f"  [{label}] {title}... ", end="", flush=True)

            result = summarize_item(client, item)
            item["key_points"] = result.get("key_points", [])
            item["industry_impact"] = result.get("industry_impact", "")
            item["related_laws"] = result.get("related_laws", [])
            week_updated = True
            updated += 1
            print("완료")
            time.sleep(0.3)  # rate limit 여유

        # 주간 요약이 없거나 항목 요약 후 재생성
        if week_updated or not week.get("weekly_summary"):
            print(f"  [{label}] 주간 요약 생성 중...")
            week["weekly_summary"] = summarize_week(client, week)

    import datetime
    archive["last_updated"] = datetime.datetime.now().isoformat()

    with open(ARCHIVE_PATH, "w", encoding="utf-8") as f:
        json.dump(archive, f, ensure_ascii=False, indent=2)

    print(f"\n완료: {updated}건 업데이트, archive.json 저장")
    print("다음 단계: python scripts/build_site.py")


if __name__ == "__main__":
    main()
