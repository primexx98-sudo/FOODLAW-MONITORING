"""Gemini API(무료 티어)를 사용해 archive.json 각 항목의 핵심 내용·업계 영향·주간 요약을 생성합니다.

2026-07-22: Anthropic Claude API(유료 크레딧 필요)에서 Google Gemini API(무료 티어)로 교체.
API 키는 https://aistudio.google.com/apikey 에서 무료로 발급받는다.

실행:
  $env:GEMINI_API_KEY="AIza..."
  python scripts/summarize_items.py
"""

import datetime
import json
import os
import re
import sys
import time

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
ARCHIVE_PATH = os.path.join(REPO_ROOT, "data", "archive.json")

MODEL = "gemini-flash-latest"
# 2026-07-23: gemini-flash-latest(=gemini-3.6-flash)는 무료 티어가 분당 5회로
# 빡빡해서, 호출 간격을 13초로 늘리고 429는 재시도 힌트(retryDelay)만큼 기다렸다가
# 한 번 더 시도한다.
CALL_INTERVAL_SEC = 13


def call_gemini(client, prompt: str) -> str:
    try:
        resp = client.models.generate_content(model=MODEL, contents=prompt)
    except Exception as e:
        msg = str(e)
        if "RESOURCE_EXHAUSTED" in msg or "429" in msg:
            wait = 30
            m = re.search(r"retryDelay['\"]?:\s*['\"]?(\d+)", msg)
            if m:
                wait = int(m.group(1)) + 2
            print(f"    429 재시도 대기 {wait}초...")
            time.sleep(wait)
            resp = client.models.generate_content(model=MODEL, contents=prompt)
        else:
            raise
    return resp.text.strip()


def summarize_item(client, item: dict) -> dict:
    title = item.get("title", "")
    source = item.get("source", "")
    status = item.get("status", "")
    date = item.get("date", "")
    law_type = item.get("law_type", "")
    body_text = item.get("body_text", "")

    if body_text:
        # 2026-07-23: 상세페이지 실제 본문(개정이유·주요내용·의견제출 등)을 그대로
        # 근거로 제공 — 이전에는 제목만 주고 "분석"을 요청해 모델이 그럴듯한 내용을
        # 지어내는 문제가 있었음. related_laws도 모델이 URL을 지어내 깨진 링크가
        # 나올 위험이 있어 제거하고, 본문에 실제로 「」로 인용된 법령명만 뽑게 함.
        prompt = f"""당신은 식품산업 법령 전문 분석가입니다.
아래는 식약처 공고 상세페이지의 실제 본문입니다. 이 본문에 실제로 적힌 내용만 근거로 분석해 JSON으로 반환하세요.
본문에 없는 내용은 절대 추측하거나 지어내지 마세요.

제목: {title}
출처: {source}
상태: {status} ({law_type})
날짜: {date}

--- 공고 본문 ---
{body_text}
--- 본문 끝 ---

다음 형식으로만 반환 (다른 텍스트 없이 JSON만):
{{
  "key_points": [
    "① [본문에 실제로 나온 변경 내용 1] — [본문 근거 간단 설명]",
    "② [본문에 실제로 나온 변경 내용 2] — [본문 근거 간단 설명]",
    "③ [본문에 실제로 나온 변경 내용 3, 있는 경우]"
  ],
  "industry_impact": "식품 제조·판매·수입 업체 관점에서 본문 내용이 실무에 미치는 영향 1~2문장",
  "related_laws": ["본문에 「」로 인용된 관련 법령명만, 없으면 빈 배열"]
}}

조건:
- key_points·industry_impact는 반드시 본문에 실제로 언급된 내용만 사용
- 의견제출 마감일이 본문에 있으면 industry_impact 또는 key_points에 반드시 포함
- related_laws는 본문에 「」로 실제 인용된 법령명만 (URL 없이 이름만, 지어내지 말 것)
- 한국어로만 작성"""
    else:
        # body_text를 못 가져온 항목(예: 상세페이지 접근 실패)에 한해서만 제목 기반 폴백 사용
        prompt = f"""당신은 식품산업 법령 전문 분석가입니다.
아래 식품 법령 개정 정보는 제목만 확인 가능합니다(본문 수집 실패). 제목에서 합리적으로 유추 가능한 범위에서만 분석해 JSON으로 반환하세요.

제목: {title}
출처: {source}
상태: {status} ({law_type})
날짜: {date}

다음 형식으로만 반환 (다른 텍스트 없이 JSON만):
{{
  "key_points": ["① 제목에서 유추 가능한 변경 사항 (제목 기반 추정임을 감안)"],
  "industry_impact": "식품 업계에 미치는 영향을 1문장으로 (제목 기반 추정)",
  "related_laws": []
}}

조건:
- 본문을 확인하지 못했으므로 과도하게 구체적인 내용은 만들지 말 것
- 한국어로만 작성"""

    text = ""
    try:
        text = call_gemini(client, prompt)
        # JSON 블록 추출
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        result = json.loads(text)
        result["summarized_with_body"] = bool(body_text)
        return result
    except Exception as e:
        print(f"    파싱 오류 ({e}): {text[:100]}")
        return {
            "key_points": [],
            "industry_impact": "",
            "related_laws": [],
            "summarized_with_body": False,
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
        return call_gemini(client, prompt)
    except Exception as e:
        print(f"    주간 요약 오류: {e}")
        return ""


def needs_update(item: dict) -> bool:
    if not item.get("key_points"):
        return True
    # body_text가 새로 백필됐는데 아직 제목만으로 요약된 상태면 근거 있는 요약으로 재생성
    if item.get("body_text") and not item.get("summarized_with_body"):
        return True
    return False


def main():
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        print("[경고] GEMINI_API_KEY 환경변수가 설정되지 않아 요약 단계를 건너뜁니다.")
        print("  발급: https://aistudio.google.com/apikey (무료)")
        print("  PowerShell: $env:GEMINI_API_KEY='AIza...'")
        print("  GitHub Actions: Settings → Secrets → GEMINI_API_KEY 등록")
        return

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
    except ImportError:
        print("[오류] google-genai 패키지가 없습니다: pip install google-genai")
        sys.exit(1)

    with open(ARCHIVE_PATH, encoding="utf-8") as f:
        archive = json.load(f)

    total_items = sum(len(w.get("items", [])) for w in archive["weeks"])

    # 2026-07-23: 2023~2026년 과거 데이터 198건을 한 번에 백필하면서 무료 티어
    # 일일 호출 한도(실측 20회)를 훨씬 초과하는 문제가 생김. 사용자 결정:
    # "가장 최근 것부터 요약하고, 그 다음 과거 자료는 하루 10건씩" —
    # 당해년도(CURRENT_YEAR) 항목은 무제한 처리(원래도 주당 2~4건 수준이라
    # 한도에 안 걸림), 그 이전 항목은 하루 HISTORICAL_ITEM_CAP건만 처리.
    # 전체 호출(항목 요약 + 주간 요약 합산)은 DAILY_TOTAL_CAP으로 다시 한 번
    # 안전장치를 둔다.
    CURRENT_YEAR = str(datetime.datetime.now().year)
    HISTORICAL_ITEM_CAP = 10
    DAILY_TOTAL_CAP = 18

    all_pairs = [
        (week, item)
        for week in archive["weeks"]
        for item in week.get("items", [])
        if needs_update(item)
    ]
    all_pairs.sort(key=lambda p: p[1].get("date", ""), reverse=True)

    recent_pairs = [p for p in all_pairs if p[1].get("date", "").startswith(CURRENT_YEAR)]
    historical_pairs = [p for p in all_pairs if not p[1].get("date", "").startswith(CURRENT_YEAR)]
    to_process = recent_pairs + historical_pairs[:HISTORICAL_ITEM_CAP]

    print(
        f"전체 {total_items}건 중 요약 필요 {len(all_pairs)}건 — "
        f"오늘 처리 대상: {CURRENT_YEAR}년 {len(recent_pairs)}건(전부) "
        f"+ 과거 {min(len(historical_pairs), HISTORICAL_ITEM_CAP)}건"
        f"(과거 잔여 {max(len(historical_pairs) - HISTORICAL_ITEM_CAP, 0)}건은 다음 실행에서)"
    )

    calls_made = 0
    touched_weeks = {}

    for week, item in to_process:
        if calls_made >= DAILY_TOTAL_CAP:
            print(f"일일 호출 한도({DAILY_TOTAL_CAP}) 도달, 남은 항목은 다음 실행에서 처리")
            break

        title = item.get("title", "")[:40]
        label = week.get("label", "")
        print(f"  [{label}] {title}... ", end="", flush=True)

        result = summarize_item(client, item)
        item["key_points"] = result.get("key_points", [])
        item["industry_impact"] = result.get("industry_impact", "")
        item["related_laws"] = result.get("related_laws", [])
        item["summarized_with_body"] = result.get("summarized_with_body", False)
        calls_made += 1
        touched_weeks[(week.get("year"), week.get("week_num"))] = week
        print("완료")
        time.sleep(CALL_INTERVAL_SEC)

    updated = calls_made

    # 주간 요약이 필요한 대상 = 이번 실행에서 항목이 갱신된 주차 + 항목은 이미 다 있는데
    # weekly_summary만 비어있는 주차(과거 실행이 일일 호출 한도에 걸려 항목 요약만 끝내고
    # 주간 요약 단계를 못 밟은 채 끝난 경우 — needs_update()가 항목 기준이라 그 주차는
    # 이후 영원히 다시 방문되지 않아 weekly_summary가 계속 비어있게 됨, 2026-07-29 발견)
    weeks_needing_summary = {
        (w.get("year"), w.get("week_num")): w
        for w in archive["weeks"]
        if w.get("items") and not w.get("weekly_summary")
    }
    weeks_needing_summary.update(touched_weeks)

    # 당해년도(사용자가 실제로 보는 최근 주차)를 과거 백필 주차보다 먼저 처리한다.
    # archive 저장 순서(과거→최근)대로 처리하면 2023년 주차가 대량으로 큐를 독점해
    # 정작 최근 주차 요약이 계속 뒤로 밀리는 문제가 있었음 (2026-07-29 발견).
    ordered_weeks = sorted(
        weeks_needing_summary.values(),
        key=lambda w: (str(w.get("year")) != CURRENT_YEAR, w.get("year"), w.get("week_num")),
    )

    for week in ordered_weeks:
        if calls_made >= DAILY_TOTAL_CAP:
            print("일일 호출 한도 도달, 주간 요약은 다음 실행에서 처리")
            break
        label = week.get("label", "")
        print(f"  [{label}] 주간 요약 생성 중...")
        week["weekly_summary"] = summarize_week(client, week)
        calls_made += 1
        time.sleep(CALL_INTERVAL_SEC)

    archive["last_updated"] = datetime.datetime.now().isoformat()

    with open(ARCHIVE_PATH, "w", encoding="utf-8") as f:
        json.dump(archive, f, ensure_ascii=False, indent=2)

    print(f"\n완료: {updated}건 업데이트, archive.json 저장")
    print("다음 단계: python scripts/build_site.py")


if __name__ == "__main__":
    main()
