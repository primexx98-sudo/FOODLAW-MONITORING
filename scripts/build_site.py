"""data/archive.json을 읽어 docs/index.html을 생성합니다."""

import hashlib
import json
import os
import re
from datetime import datetime

from category_utils import CATEGORY_META, CATEGORY_ORDER, categorize_item

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
ARCHIVE_PATH = os.path.join(REPO_ROOT, "data", "archive.json")
OUTPUT_PATH = os.path.join(REPO_ROOT, "docs", "index.html")

CIRCLES = "①②③④⑤⑥⑦⑧⑨⑩"

SOURCE_COLORS = {
    "식약처": "tag-green",
}
STATUS_COLORS = {
    "시행": "status-enforce",
    "예고": "status-notice",
    "공포": "status-pub",
    "공고": "status-pub",
}

INTEREST_KEYWORDS = ["건강기능식품", "기능성", "건기식"]

LABEL_SPOTLIGHT_CATEGORY = "표시기준"
LABEL_SPOTLIGHT_LIMIT = 12


def is_interest(item):
    text = item.get("title", "") + item.get("law_type", "")
    return any(kw in text for kw in INTEREST_KEYWORDS)


def esc(text):
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def item_anchor_id(item):
    """항목별 고유 앵커 id — health-trend의 "오늘의 요약"이 같은 값으로 계산해
    #law-xxxxx 딥링크를 만들 수 있도록, url(없으면 title)을 md5 해시해 생성한다.
    두 프로젝트가 서로 다른 코드베이스이므로 알고리즘(md5 hexdigest 앞 10자)이
    한쪽만 바뀌면 링크가 깨진다 — 바꿀 때는 health-trend의 동일 함수도 같이 수정."""
    key = item.get("url") or item.get("title", "")
    return "law-" + hashlib.md5(key.encode("utf-8")).hexdigest()[:10]


def render_key_points(key_points):
    if not key_points:
        return ""
    rows = ""
    for i, pt in enumerate(key_points):
        circle = CIRCLES[i] if i < len(CIRCLES) else f"{i+1}."
        rows += f'<li><span class="kp-num">{circle}</span><span class="kp-text">{esc(pt)}</span></li>\n'
    return f'<div class="section-label">핵심 내용</div><ul class="key-points">{rows}</ul>'


EXCERPT_MAX_CHARS = 500


def extract_excerpt(body_text):
    """AI 요약이 아직 없는 항목(대부분 2023~2025년 백로그, 하루 10건 제한으로
    순차 처리 중)도 상세페이지에서 이미 수집해둔 실제 본문(body_text)이 있으면 그걸
    그대로 보여준다 — 기다릴 필요 없이 즉시 확인 가능하고, 원문이라 지어낼 위험도 없음.
    "개정이유 및 주요내용" 섹션을 우선 추출하고, 못 찾으면 본문 앞부분을 그대로 보여준다."""
    if not body_text:
        return ""
    # 공고마다 "개정이유 및 주요내용"/"개정 이유"+"주요 내용" 등 띄어쓰기·분리 방식이
    # 다름. 앞머리 안내문("...개정 이유 및 주요 내용을 「행정절차법」에 따라 공고합니다")에도
    # "개정 이유"라는 말이 인라인으로 섞여 있어 그냥 찾으면 그 문장에서 멈춰버리므로,
    # 반드시 "1." 로 시작하는 번호 매긴 섹션 제목만 매칭한다.
    m = re.search(r"1\.\s*개정\s*이유", body_text)
    if not m:
        excerpt = body_text
    else:
        rest = body_text[m.start():]
        end_markers = ["\n2. 의견제출", "\n2.의견제출", "2. 의견제출", "\n의견제출"]
        end = len(rest)
        for em in end_markers:
            p = rest.find(em)
            if p != -1:
                end = min(end, p)
        excerpt = rest[:end].strip()
    excerpt = excerpt.strip()
    if len(excerpt) > EXCERPT_MAX_CHARS:
        excerpt = excerpt[:EXCERPT_MAX_CHARS].rstrip() + "…"
    return excerpt


def render_raw_excerpt(body_text):
    excerpt = extract_excerpt(body_text)
    if not excerpt:
        return ""
    return (
        '<div class="section-label">원문 발췌 (AI 요약 대기 중)</div>'
        f'<div class="raw-excerpt">{esc(excerpt)}</div>'
    )


def render_impact(impact):
    if not impact:
        return ""
    return f'<div class="impact-box">💡 <strong>업계 영향</strong> — {esc(impact)}</div>'


def render_related_laws(related_laws, source_url):
    # 2026-07-23: related_laws는 더 이상 URL을 포함하지 않음 — 예전엔 Gemini/Claude가
    # law.go.kr URL을 스스로 지어내 깨진 링크가 나올 위험이 있었음. 이제 본문에 실제
    # 「」로 인용된 법령명만 텍스트 배지로 표시(클릭 불가), 실제 링크는 원문 하나만 제공.
    tags = []
    if related_laws:
        for law in related_laws:
            name = law.get("title") if isinstance(law, dict) else law
            if name:
                tags.append(f'<span class="law-tag">📄 {esc(name)}</span>')
    # 2026-08-19: 수집 시 원문 링크를 확보 못한 항목(source_url 없음, list.do로만
    # 잡히던 과거 버그)은 "원문 바로가기"를 눌러도 목록 페이지로 가는 깨진 링크가
    # 되므로, 버튼 대신 안내 문구만 보여준다(collect_mfds.py 쪽 로그도 참고).
    if source_url and not source_url.endswith("/list.do"):
        link_html = f'<a class="btn-original" href="{esc(source_url)}" target="_blank" rel="noopener">원문 바로가기</a>'
    else:
        link_html = '<span class="btn-original-disabled">원문 링크 확인 불가</span>'
    return f"""
    <div class="law-footer">
      {link_html}
      {"".join(tags)}
    </div>"""


SEARCH_TEXT_MAX_CHARS = 400


def build_search_text(item):
    """검색창(클라이언트 사이드)이 매칭할 대상 텍스트 — 제목+핵심내용+업계영향+
    관련법령명까지 포함시켜 제목만으로는 못 찾는 항목도 검색되게 한다."""
    parts = [item.get("title", "")]
    parts.extend(item.get("key_points") or [])
    if item.get("industry_impact"):
        parts.append(item["industry_impact"])
    for law in item.get("related_laws") or []:
        name = law.get("title") if isinstance(law, dict) else law
        if name:
            parts.append(name)
    if not item.get("key_points"):
        parts.append((item.get("body_text") or "")[:SEARCH_TEXT_MAX_CHARS])
    return " ".join(parts).lower()


def category_chip(category):
    meta = CATEGORY_META[category]
    return f'<span class="tag cat-tag {meta["css"]}">{meta["icon"]} {esc(meta["label"])}</span>'


def render_preview_line(key_points):
    """접힌 상태에서도 핵심 내용을 한 줄 미리 보여준다 — 클릭해서 펼쳐야만 내용을
    알 수 있었던 정보 밀도 문제(사용자 피드백)를 해소하기 위해 추가."""
    if not key_points:
        return ""
    first = key_points[0]
    if len(first) > 90:
        first = first[:90].rstrip() + "…"
    return f'<div class="law-preview">{esc(first)}</div>'


def render_item(item):
    title = esc(item.get("title", ""))
    source = item.get("source", "")
    status = item.get("status", "")
    date = esc(item.get("date", ""))
    url = item.get("url", "#")
    key_points = item.get("key_points", [])
    impact = item.get("industry_impact", "")
    related_laws = item.get("related_laws", [])
    body_text = item.get("body_text", "")
    is_new = item.get("is_new", False)
    category = item.get("_category", "기타")

    src_cls = SOURCE_COLORS.get(source, "tag-gray")
    st_cls = STATUS_COLORS.get(status, "status-info")
    new_badge = '<span class="badge-new">NEW</span>' if is_new else ""
    interest_badge = '<span class="tag tag-interest">관심</span>' if is_interest(item) else ""

    # key_points(AI 요약)가 아직 없으면 원문 발췌로 대체 — 하루 10건 제한으로
    # 요약이 순차 처리 중인 과거 항목(2023~2025)도 즉시 내용을 볼 수 있게 함
    if key_points:
        main_html = render_key_points(key_points)
    else:
        main_html = render_raw_excerpt(body_text)

    body_html = main_html + render_impact(impact) + render_related_laws(related_laws, url)
    has_body = bool(key_points or impact or related_laws or body_text)
    expandable = "expandable" if has_body else ""
    search_text = esc(build_search_text(item))
    anchor_id = item_anchor_id(item)

    return f"""
<div class="law-item {expandable}" id="{anchor_id}" data-source="{esc(source)}" data-status="{esc(status)}" data-category="{esc(category)}" data-date="{date}" data-search="{search_text}">
  <div class="law-header" onclick="toggleItem(this)">
    <div class="law-tags">
      <span class="tag {st_cls}">{esc(status)}</span>
      <span class="tag {src_cls}">{esc(source)}</span>
      {category_chip(category)}
      {interest_badge}
      {new_badge}
    </div>
    <div class="law-title">{title}</div>
    {render_preview_line(key_points)}
    <div class="law-meta">
      <span class="law-date">📅 {date} {esc(status)}</span>
      {"<span class='law-arrow'>▾</span>" if has_body else ""}
    </div>
  </div>
  {"<div class='law-body'>" + body_html + "</div>" if has_body else ""}
</div>"""


def render_group(items, label, icon):
    if not items:
        return ""
    items_html = "".join(render_item(it) for it in items)
    count = len(items)
    return f"""
<div class="group-section">
  <div class="group-header">
    <span class="group-dot {icon}"></span>
    <span class="group-label">{esc(label)}</span>
    <span class="group-count">{count}건</span>
  </div>
  {items_html}
</div>"""


def render_week(week, index):
    items = week.get("items", [])
    counts = week.get("counts", {})
    label = week.get("label", "")
    year = week.get("year", "")
    week_num = week.get("week_num", "")
    start = week.get("start_date", "")
    end = week.get("end_date", "")
    total = counts.get("total", len(items))
    weekly_summary = week.get("weekly_summary", week.get("summary", ""))

    is_latest = index == 0
    open_cls = "open" if is_latest else ""
    btn_open = "open" if is_latest else ""

    enforce_items = [it for it in items if it.get("status") in ("시행", "공포", "공고")]
    notice_items = [it for it in items if it.get("status") in ("예고",)]
    other_items = [it for it in items if it not in enforce_items and it not in notice_items]

    groups_html = (
        render_group(enforce_items, "해당 시행 — 이번 주 확인된 확정 법령", "dot-enforce")
        + render_group(notice_items, "확정예고 입법 — 미래발령, 지속 추적", "dot-notice")
        + render_group(other_items, "기타", "dot-other")
    )
    if not items:
        groups_html = '<p class="no-items">이번 주 수집된 항목이 없습니다.</p>'

    copy_btn = f'<button class="btn-copy" onclick="copyText(this, \'{esc(weekly_summary)}\')">요약 복사</button>' if weekly_summary else ""
    summary_date = start.replace("-", ".")[:10] if start else ""

    # 2026-08-20: 119주차를 훑어볼 때 어떤 주에 어떤 성격의 항목이 있는지 열어보지
    # 않고도 짐작할 수 있게, 그 주에 실제 등장한 카테고리만 색점으로 표시한다
    # (유형별 현황 카드와 동일한 색상 매핑 재사용 — 새 범례를 만들지 않음).
    present_cats = {it.get("_category") for it in items}
    cat_dots_html = "".join(
        f'<span class="week-cat-dot {CATEGORY_META[c]["css"]}" title="{esc(CATEGORY_META[c]["label"])}"></span>'
        for c in CATEGORY_ORDER if c in present_cats
    )

    return f"""
<div class="week-section" data-year="{esc(year)}" id="week-{esc(year)}-{esc(week_num)}">
  <button class="accordion-btn {btn_open}" onclick="toggleWeek(this)">
    <div class="week-left">
      <span class="week-num">{esc(year)}년 {esc(week_num)}주차</span>
      <span class="week-range">{esc(start).replace("-", ".")} ~ {esc(end)[5:].replace("-", ".")}</span>
      <span class="week-cat-dots">{cat_dots_html}</span>
    </div>
    <div class="week-right">
      {"<span class='badge-latest'>최신</span>" if is_latest else ""}
      <span class="week-count">{total}건</span>
      <span class="week-arrow">{"▴" if is_latest else "▾"}</span>
    </div>
  </button>
  <div class="week-content {open_cls}">
    {"<div class='summary-box'><div class='summary-title'><span class='summary-badge'>AI 요약</span>이번 주 통합 요약 (" + esc(summary_date) + ")" + "</div><p class='summary-text'>" + esc(weekly_summary) + "</p>" + copy_btn + "</div>" if weekly_summary else ""}
    <div class="groups-wrap">
      {groups_html}
    </div>
  </div>
</div>"""


def render_category_overview(category_counts, total_items):
    cards = [
        f'''<button class="cat-card active" data-cat-btn data-cat="all" onclick="setCategory(this,'all')">
      <span class="cat-card-icon">📋</span>
      <span class="cat-card-label">전체</span>
      <span class="cat-card-count">{total_items}<small>건</small></span>
    </button>'''
    ]
    for cat in CATEGORY_ORDER:
        meta = CATEGORY_META[cat]
        count = category_counts.get(cat, 0)
        highlight = " cat-card-priority" if cat == LABEL_SPOTLIGHT_CATEGORY else ""
        cards.append(f'''<button class="cat-card {meta["css"]}{highlight}" data-cat-btn data-cat="{cat}" onclick="setCategory(this,'{cat}')">
      <span class="cat-card-icon">{meta["icon"]}</span>
      <span class="cat-card-label">{esc(meta["label"])}</span>
      <span class="cat-card-count">{count}<small>건</small></span>
    </button>''')
    return f"""
<div class="cat-overview">
  <div class="cat-overview-title">유형별 현황 <span class="cat-overview-sub">— 클릭하면 바로 아래에 해당 유형 목록이 펼쳐집니다</span></div>
  <div class="cat-grid">
    {"".join(cards)}
  </div>
  <div class="cat-dropdown" id="catDropdown" hidden></div>
</div>"""


def render_label_spotlight(spotlight_items):
    meta = CATEGORY_META[LABEL_SPOTLIGHT_CATEGORY]
    if not spotlight_items:
        body = '<p class="no-items">아직 표시사항 변경 항목이 수집되지 않았습니다.</p>'
    else:
        rows = []
        for it in spotlight_items:
            status = it.get("status", "")
            st_cls = STATUS_COLORS.get(status, "status-info")
            it_url = it.get("url", "")
            has_link = bool(it_url) and not it_url.endswith("/list.do")
            tag_name = "a" if has_link else "div"
            href_attr = f'href="{esc(it_url)}" target="_blank" rel="noopener"' if has_link else ""
            # 업계 영향(industry_impact) 요약이 있으면 우선 노출, 없으면 핵심 포인트 첫 항목으로 대체
            summary_text = it.get("industry_impact") or ""
            if not summary_text:
                kp = it.get("key_points") or []
                summary_text = kp[0] if kp else ""
            summary_html = (
                f'\n      <span class="spotlight-summary">{esc(summary_text)}</span>'
                if summary_text else ""
            )
            rows.append(f"""
    <{tag_name} class="spotlight-item" {href_attr}>
      <span class="tag {st_cls}">{esc(status)}</span>
      <span class="spotlight-title">{esc(it.get('title', ''))}</span>
      <span class="spotlight-meta">{esc(it.get('date', ''))} · {esc(it.get('_week_label', ''))}</span>{summary_html}
    </{tag_name}>""")
        body = "".join(rows)
    return f"""
<div class="card label-spotlight">
  <div class="card-header cat-label-header">{meta["icon"]} 표시사항 변경 추적 — 최근 {len(spotlight_items)}건</div>
  <div class="label-spotlight-body">
    {body}
  </div>
</div>"""


def render_monthly_summary(months_data):
    """월 단위 AI 통합 요약 카드. 요약 텍스트가 아직 없는 달(요약 배치 처리 대기 중)은
    건너뛰고, 요약이 있는 달만 최신순으로 아코디언 목록으로 보여준다."""
    entries = sorted(
        ((mk, m) for mk, m in months_data.items() if m.get("monthly_summary")),
        key=lambda kv: kv[0],
        reverse=True,
    )
    if not entries:
        return ""
    rows = []
    for i, (mk, m) in enumerate(entries):
        label = m.get("label", mk)
        summary = m.get("monthly_summary", "")
        count = m.get("item_count", 0)
        open_cls = "open" if i == 0 else ""
        rows.append(f"""
    <div class="month-section">
      <button class="month-btn {open_cls}" onclick="toggleWeek(this)">
        <span class="month-label">{esc(label)}</span>
        <span class="month-count">{count}건</span>
        <span class="week-arrow">{"▴" if i == 0 else "▾"}</span>
      </button>
      <div class="month-content {open_cls}">
        <p class="summary-text">{esc(summary)}</p>
        <button class="btn-copy" onclick="copyText(this, '{esc(summary)}')">요약 복사</button>
      </div>
    </div>""")
    return f"""
<div class="card monthly-summary">
  <div class="card-header cat-label-header">🗓️ 월간 통합 요약</div>
  <div class="monthly-summary-body">
    {"".join(rows)}
  </div>
</div>"""


def build():
    if not os.path.exists(ARCHIVE_PATH):
        weeks, total_weeks, last_updated, months_data = [], 0, "", {}
    else:
        with open(ARCHIVE_PATH, encoding="utf-8") as f:
            archive = json.load(f)
        # 저장 순서와 무관하게 항상 최신 주차가 맨 위로 오도록 정렬
        weeks = sorted(
            archive.get("weeks", []),
            key=lambda w: (w.get("year", 0), w.get("week_num", 0)),
            reverse=True,
        )
        total_weeks = archive.get("total_weeks", len(weeks))
        last_updated = archive.get("last_updated", "")
        # 월간 요약(AI 생성)은 summarize_items.py가 archive.json["months"]에 미리
        # 저장해둔 값을 그대로 읽어 보여준다 — build_site.py는 재계산하지 않음.
        months_data = archive.get("months", {})

    # 카테고리는 archive.json에 저장하지 않고 매 빌드마다 순수 함수로 재계산 —
    # 과거 항목에도 즉시 적용되고, 분류 로직을 바꿔도 재수집 없이 바로 반영됨.
    flat_items = []
    category_counts = {}
    for w in weeks:
        week_label = w.get("label") or f"{w.get('year', '')}년 {w.get('week_num', '')}주차"
        for it in w.get("items", []):
            cat = categorize_item(it)
            it["_category"] = cat
            it["_week_label"] = week_label
            category_counts[cat] = category_counts.get(cat, 0) + 1
            flat_items.append(it)

    label_spotlight_items = sorted(
        [it for it in flat_items if it["_category"] == LABEL_SPOTLIGHT_CATEGORY],
        key=lambda x: x.get("date", ""),
        reverse=True,
    )[:LABEL_SPOTLIGHT_LIMIT]

    years = sorted({w.get("year") for w in weeks if w.get("year")}, reverse=True)
    default_year = years[0] if years else ""
    year_btns_html = "".join(
        f'<button class="filter-btn{" active" if y == default_year else ""}" onclick="setYear(this,\'{y}\')">{y}년</button>'
        for y in years
    )

    latest = weeks[0] if weeks else {}
    lc = latest.get("counts", {})
    kpi_total = lc.get("total", 0)
    kpi_enforce = lc.get("시행", 0)
    kpi_notice = lc.get("예고", 0)
    all_items = len(flat_items)

    archive_text = "\n\n".join(
        f"[{w.get('label', '')} {w.get('start_date', '')}~{w.get('end_date', '')}]\n"
        + (w.get("weekly_summary") or w.get("summary", ""))
        for w in weeks
        if w.get("items")
    )

    try:
        updated_str = datetime.fromisoformat(last_updated).strftime("%Y.%m.%d")
    except Exception:
        updated_str = datetime.now().strftime("%Y.%m.%d")

    weeks_html = "".join(render_week(w, i) for i, w in enumerate(weeks)) or \
        '<p class="no-items" style="padding:40px;text-align:center;">아직 데이터가 없습니다.</p>'

    cat_overview_html = render_category_overview(category_counts, all_items)
    label_spotlight_html = render_label_spotlight(label_spotlight_items)
    monthly_summary_html = render_monthly_summary(months_data)

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>식품 법령 개정 모니터</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">
  <script>
    // 2026-07-23: 라이트/다크 토글 — 저장된 값을 CSS보다 먼저 적용해 첫 렌더 시
    // 깜빡임(잘못된 테마로 그렸다가 바뀌는 현상) 없이 바로 맞는 테마로 뜨게 함
    (function() {{
      var saved = localStorage.getItem('theme');
      if (saved === 'light' || saved === 'dark') {{
        document.documentElement.setAttribute('data-theme', saved);
      }}
    }})();
  </script>
  <style>
    *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
    /* 2026-08-19: 트렌드 대시보드(health-trend)와 동일한 Binance 다크테마 토큰으로 통일
       — 두 대시보드가 허브(food-monitor-hub) 안에서 서로 다른 룩앤필이던 문제 해소 */
    :root{{
      --canvas:#0b0e11;--surface:#1e2329;--surface-elevated:#2b3139;
      --hairline:#2b3139;--body-text:#eaecef;--muted:#707a8a;--muted-strong:#929aa5;
      --primary:#fcd535;--primary-text:#fcd535;--primary-active:#f0b90b;
      --up:#0ecb81;--down:#f6465d;--info:#3b82f6;--turquoise:#2dbdb6;
    }}
    :root[data-theme="light"]{{
      --canvas:#f7f8fa;--surface:#ffffff;--surface-elevated:#f0f2f5;
      --hairline:#e6e8eb;--body-text:#1e2329;--muted:#76808f;--muted-strong:#4b5563;
      --primary:#fcd535;--primary-text:#9a7300;--primary-active:#b8860b;
      --up:#0a9f68;--down:#d63447;--info:#2563eb;--turquoise:#0f8f88;
    }}
    body{{font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI','Apple SD Gothic Neo','Noto Sans KR',sans-serif;
      background:var(--canvas);color:var(--body-text);font-size:14px;line-height:1.65;}}
    .mono{{font-family:'JetBrains Mono',monospace;}}

    /* ── HEADER ── */
    .site-header{{
      background:var(--canvas);border-bottom:1px solid var(--hairline);
      padding:14px 24px 12px;
      display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:10px;
    }}
    .header-left{{display:flex;flex-direction:column;gap:2px;}}
    .header-left h1{{font-size:1.15rem;font-weight:700;color:var(--body-text);letter-spacing:-.3px;}}
    .header-left h1 svg{{vertical-align:middle;margin-right:6px;color:var(--primary-text);}}
    .header-left p{{font-size:0.75rem;color:var(--muted);margin-top:3px;}}
    .header-titlerow{{display:flex;align-items:center;gap:8px;}}
    .header-right{{display:flex;gap:6px;flex-wrap:wrap;align-items:center;}}
    .hbadge{{background:var(--surface-elevated);border:1px solid var(--hairline);
      border-radius:4px;padding:3px 9px;font-size:0.72rem;color:var(--muted-strong);}}
    .hbadge.accent{{background:rgba(252,213,53,.12);color:var(--primary-text);border-color:rgba(252,213,53,.35);}}
    .theme-toggle{{
      background:var(--surface-elevated);border:1px solid var(--hairline);
      color:var(--body-text);height:26px;padding:0 10px;border-radius:13px;cursor:pointer;
      display:inline-flex;align-items:center;gap:5px;justify-content:center;
      font-size:0.72rem;font-weight:600;flex-shrink:0;line-height:1;white-space:nowrap;
    }}
    .theme-toggle:hover{{background:var(--hairline);}}

    /* ── TOOLBAR ── */
    .toolbar{{
      background:var(--canvas);border-bottom:1px solid var(--hairline);
      padding:7px 24px;display:flex;align-items:center;gap:8px;flex-wrap:wrap;
    }}
    .toolbar-info{{font-size:0.8rem;color:var(--muted);flex:1;}}
    .toolbar-info b{{color:var(--primary-text);}}
    .btn-tool{{
      background:var(--surface);border:1px solid var(--hairline);color:var(--body-text);
      padding:4px 11px;border-radius:4px;font-size:0.78rem;cursor:pointer;
    }}
    .btn-tool:hover{{background:var(--surface-elevated);}}

    /* ── SEARCH ── */
    .search-box{{
      display:flex;align-items:center;gap:6px;background:var(--surface-elevated);
      border:1px solid var(--hairline);border-radius:8px;padding:0 10px;height:32px;
      flex:1;max-width:320px;min-width:160px;
    }}
    .search-icon{{font-size:0.8rem;opacity:0.7;flex-shrink:0;}}
    .search-input{{
      background:transparent;border:none;outline:none;color:var(--body-text);
      font-size:0.82rem;font-family:'Inter',sans-serif;flex:1;min-width:0;
    }}
    .search-input::placeholder{{color:var(--muted);}}
    .search-clear{{
      background:none;border:none;color:var(--muted);cursor:pointer;
      font-size:0.78rem;padding:2px 4px;flex-shrink:0;
    }}
    .search-clear:hover{{color:var(--body-text);}}
    .search-status{{
      padding:6px 24px;font-size:0.78rem;color:var(--muted);background:var(--canvas);
      border-bottom:1px solid var(--hairline);
      display:flex;align-items:center;gap:10px;flex-wrap:wrap;
    }}
    .search-status b{{color:var(--primary-text);}}
    .status-clear-btn{{
      background:none;border:1px solid var(--hairline);color:var(--muted);
      padding:2px 9px;border-radius:20px;font-size:0.72rem;cursor:pointer;
    }}
    .status-clear-btn:hover{{background:var(--surface-elevated);color:var(--body-text);}}

    /* ── FILTER ── */
    .filter-bar{{
      background:var(--canvas);border-bottom:1px solid var(--hairline);
      padding:7px 24px;display:flex;gap:6px;flex-wrap:wrap;align-items:center;
    }}
    .filter-label{{font-size:0.74rem;color:var(--muted);}}
    .filter-sep{{width:1px;height:14px;background:var(--hairline);margin:0 4px;}}
    .year-filter-group{{display:contents;}}
    .year-filter-group[hidden]{{display:none;}}
    .filter-btn{{
      background:transparent;border:1px solid var(--hairline);color:var(--muted);
      padding:3px 11px;border-radius:20px;font-size:0.75rem;cursor:pointer;
    }}
    .filter-btn.active{{background:rgba(252,213,53,.15);border-color:var(--primary);color:var(--primary-text);}}

    /* ── KPI ── */
    .kpi-row{{
      display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));
      gap:8px;padding:14px 24px;background:var(--canvas);border-bottom:1px solid var(--hairline);
    }}
    .kpi{{background:var(--surface);border:none;border-radius:12px;
      padding:12px 15px;border-left:3px solid var(--primary);}}
    .kpi.blue{{border-left-color:var(--info);}}
    .kpi.orange{{border-left-color:var(--primary);}}
    .kpi.red{{border-left-color:var(--down);}}
    .kpi-label{{font-size:0.72rem;color:var(--muted);margin-bottom:4px;}}
    .kpi-val{{font-size:1.35rem;font-weight:700;font-family:'JetBrains Mono',monospace;}}
    .kpi-unit{{font-size:0.7rem;color:var(--muted);}}

    /* ── CATEGORY OVERVIEW ── */
    .cat-overview{{padding:16px 24px 4px;background:var(--canvas);}}
    .cat-overview-title{{font-size:0.85rem;font-weight:700;color:var(--body-text);margin-bottom:10px;}}
    .cat-overview-sub{{font-weight:400;color:var(--muted);font-size:0.76rem;}}
    .cat-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:8px;margin-bottom:14px;}}
    .cat-card{{
      background:var(--surface);border:1px solid var(--hairline);border-radius:10px;
      padding:10px 12px;cursor:pointer;text-align:left;display:flex;flex-direction:column;gap:4px;
      color:var(--body-text);transition:border-color .15s;
    }}
    .cat-card:hover{{border-color:var(--muted-strong);}}
    .cat-card.active{{border-color:var(--primary);box-shadow:0 0 0 1px var(--primary) inset;}}
    .cat-card-priority{{border-color:rgba(252,213,53,.4);}}
    .cat-card-icon{{font-size:1.1rem;}}
    .cat-card-label{{font-size:0.76rem;color:var(--muted-strong);font-weight:600;}}
    .cat-card-count{{font-size:1.15rem;font-weight:700;font-family:'JetBrains Mono',monospace;color:var(--body-text);}}
    .cat-card-count small{{font-size:0.65rem;font-weight:500;color:var(--muted);margin-left:2px;}}
    .cat-dropdown{{
      background:var(--surface);border:1px solid var(--hairline);border-radius:10px;
      padding:12px;margin-bottom:14px;
    }}
    .cat-dropdown-status{{font-size:0.78rem;color:var(--muted);padding:2px 2px 10px;}}
    .cat-dropdown-status b{{color:var(--primary-text);}}
    .cat-card-count small{{font-size:0.65rem;font-weight:500;color:var(--muted);margin-left:2px;}}

    /* ── LABEL SPOTLIGHT ── */
    .card{{background:var(--surface);border:none;border-radius:12px;margin:0 24px 16px;overflow:hidden;}}
    .card-header{{background:transparent;color:var(--body-text);border-bottom:1px solid var(--hairline);
      font-weight:700;font-size:0.92rem;padding:12px 16px;}}
    .cat-label-header{{border-bottom-color:var(--primary);}}
    .label-spotlight-body{{padding:6px 8px;}}
    .spotlight-item{{
      display:flex;flex-wrap:wrap;align-items:center;gap:4px 10px;padding:8px 8px;border-bottom:1px solid var(--hairline);
      text-decoration:none;color:var(--body-text);
    }}
    .spotlight-item:last-child{{border-bottom:none;}}
    .spotlight-item:hover{{background:var(--surface-elevated);}}
    .spotlight-title{{flex:1;font-size:0.85rem;line-height:1.4;min-width:0;}}
    .spotlight-meta{{font-size:0.72rem;color:var(--muted);white-space:nowrap;flex-shrink:0;}}
    /* 건별 요약(업계 영향) — 항상 다음 줄 전체 너비로, 2줄까지만 표시 */
    .spotlight-summary{{
      order:3;flex-basis:100%;font-size:0.78rem;line-height:1.5;color:var(--muted);margin-top:2px;
      display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;
    }}

    /* ── MAIN ── */
    .main{{max-width:860px;margin:0 auto;padding:14px 20px 80px;}}

    /* ── WEEK ── */
    .week-section{{
      background:var(--surface);border:none;
      border-radius:12px;margin-bottom:10px;overflow:hidden;
    }}
    .week-section.hidden{{display:none;}}
    .accordion-btn{{
      width:100%;background:none;border:none;padding:12px 18px;
      display:flex;justify-content:space-between;align-items:center;cursor:pointer;color:var(--body-text);
    }}
    .accordion-btn:hover{{background:var(--surface-elevated);}}
    .week-left{{display:flex;align-items:center;gap:14px;min-width:0;}}
    .week-num{{font-size:1rem;font-weight:700;color:var(--primary-text);flex-shrink:0;}}
    .week-range{{font-size:0.8rem;color:var(--muted);font-family:'JetBrains Mono',monospace;flex-shrink:0;}}
    .week-cat-dots{{display:flex;align-items:center;gap:4px;flex-wrap:wrap;}}
    .week-cat-dot{{width:7px;height:7px;border-radius:50%;flex-shrink:0;}}
    .week-cat-dot.cat-label{{background:var(--primary);}}
    .week-cat-dot.cat-spec{{background:var(--info);}}
    .week-cat-dot.cat-safety{{background:var(--up);}}
    .week-cat-dot.cat-trade{{background:var(--turquoise);}}
    .week-cat-dot.cat-biz{{background:var(--muted-strong);}}
    .week-cat-dot.cat-etc{{background:var(--muted);}}
    .week-right{{display:flex;align-items:center;gap:7px;flex-shrink:0;}}
    .badge-latest{{background:var(--down);color:#fff;font-size:0.68rem;font-weight:700;padding:2px 6px;border-radius:3px;}}
    .week-count{{background:rgba(252,213,53,.15);color:var(--primary-text);font-size:0.75rem;font-weight:600;padding:2px 8px;border-radius:4px;font-family:'JetBrains Mono',monospace;}}
    .week-arrow{{font-size:0.8rem;color:var(--muted);transition:transform .2s;}}
    .accordion-btn.open .week-arrow{{transform:rotate(180deg);}}
    .week-content{{display:none;border-top:1px solid var(--hairline);}}
    .week-content.open{{display:block;}}

    /* ── MONTHLY SUMMARY ── */
    .monthly-summary-body{{padding:6px 8px;}}
    .month-section{{border-bottom:1px solid var(--hairline);}}
    .month-section:last-child{{border-bottom:none;}}
    .month-btn{{
      width:100%;background:none;border:none;padding:10px 10px;
      display:flex;justify-content:space-between;align-items:center;gap:10px;cursor:pointer;color:var(--body-text);
    }}
    .month-btn:hover{{background:var(--surface-elevated);}}
    .month-label{{font-size:0.92rem;font-weight:700;color:var(--primary-text);}}
    .month-count{{background:rgba(252,213,53,.15);color:var(--primary-text);font-size:0.72rem;font-weight:600;padding:2px 8px;border-radius:4px;font-family:'JetBrains Mono',monospace;margin-left:auto;}}
    .month-btn.open .week-arrow{{transform:rotate(180deg);}}
    .month-content{{display:none;padding:2px 14px 14px;}}
    .month-content.open{{display:block;}}

    /* ── SUMMARY BOX ── */
    .summary-box{{
      background:var(--surface-elevated);border-bottom:1px solid var(--hairline);
      border-left:3px solid var(--primary);
      padding:14px 18px 14px 15px;
    }}
    .summary-title{{
      font-size:0.8rem;color:var(--primary-text);font-weight:600;margin-bottom:8px;
      display:flex;align-items:center;gap:8px;
    }}
    .summary-badge{{
      background:var(--primary);color:#1e2329;font-size:0.65rem;font-weight:700;
      padding:2px 8px;border-radius:10px;letter-spacing:.2px;
    }}
    .summary-text{{font-size:0.87rem;color:var(--body-text);line-height:1.75;}}
    .btn-copy{{
      display:inline-flex;align-items:center;gap:5px;
      margin-top:10px;background:var(--surface);border:1px solid var(--hairline);
      color:var(--muted);padding:4px 11px;border-radius:4px;font-size:0.75rem;cursor:pointer;
    }}
    .btn-copy:hover{{background:var(--surface-elevated);color:var(--body-text);}}
    .btn-copy.copied{{color:var(--up);border-color:var(--up);}}

    /* ── GROUPS ── */
    .groups-wrap{{padding:10px 14px 14px;}}
    .group-section{{margin-bottom:12px;}}
    .group-header{{
      display:flex;align-items:center;gap:8px;
      padding:6px 0;margin-bottom:6px;
      border-bottom:1px dashed var(--hairline);
    }}
    .group-dot{{width:8px;height:8px;border-radius:50%;flex-shrink:0;}}
    .dot-enforce{{background:var(--up);}}
    .dot-notice{{background:var(--primary);}}
    .dot-other{{background:var(--muted);}}
    .group-label{{font-size:0.77rem;color:var(--muted);flex:1;}}
    .group-count{{font-size:0.74rem;color:var(--muted);}}

    /* ── LAW ITEM ── */
    .law-item{{
      background:var(--surface-elevated);border:none;
      border-radius:8px;margin-bottom:7px;overflow:hidden;
    }}
    .law-item.hidden{{display:none;}}
    @keyframes deepLinkPulse{{0%,100%{{box-shadow:0 0 0 0 rgba(252,213,53,0);}}50%{{box-shadow:0 0 0 4px rgba(252,213,53,.55);}}}}
    .law-item.deep-link-highlight{{animation:deepLinkPulse 1s ease-in-out 2;border-radius:8px;}}
    .law-header{{padding:11px 14px;cursor:pointer;}}
    .law-item.expandable .law-header:hover{{background:rgba(255,255,255,0.03);}}
    .law-tags{{display:flex;gap:5px;flex-wrap:wrap;align-items:center;margin-bottom:6px;}}
    .tag{{display:inline-block;padding:2px 7px;border-radius:3px;font-size:0.7rem;font-weight:600;}}
    .tag-green{{background:rgba(14,203,129,.15);color:var(--up);border:1px solid rgba(14,203,129,.3);}}
    .tag-gray{{background:var(--surface);color:var(--muted);border:1px solid var(--hairline);}}
    .tag-interest{{background:rgba(45,189,182,.15);color:var(--turquoise);border:1px solid rgba(45,189,182,.35);}}
    .cat-tag{{border:1px solid transparent;}}
    .cat-label{{background:rgba(252,213,53,.15);color:var(--primary-text);border-color:rgba(252,213,53,.35);}}
    .cat-spec{{background:rgba(59,130,246,.15);color:var(--info);border-color:rgba(59,130,246,.35);}}
    .cat-safety{{background:rgba(14,203,129,.15);color:var(--up);border-color:rgba(14,203,129,.3);}}
    .cat-trade{{background:rgba(45,189,182,.15);color:var(--turquoise);border-color:rgba(45,189,182,.35);}}
    .cat-biz{{background:rgba(146,154,165,.15);color:var(--muted-strong);border-color:rgba(146,154,165,.3);}}
    .cat-etc{{background:rgba(112,122,138,.12);color:var(--muted);border-color:rgba(112,122,138,.25);}}
    .status-enforce{{background:rgba(14,203,129,.2);color:var(--up);border:1px solid rgba(14,203,129,.4);}}
    .status-notice{{background:rgba(252,213,53,.2);color:var(--primary-text);border:1px solid rgba(252,213,53,.4);}}
    .status-pub{{background:rgba(59,130,246,.2);color:var(--info);border:1px solid rgba(59,130,246,.4);}}
    .status-info{{background:var(--surface);color:var(--muted);border:1px solid var(--hairline);}}
    .badge-new{{background:var(--down);color:#fff;font-size:0.66rem;font-weight:700;padding:2px 5px;border-radius:3px;}}
    .law-title{{font-size:0.9rem;font-weight:600;line-height:1.45;margin-bottom:4px;}}
    .law-preview{{font-size:0.78rem;color:var(--muted);line-height:1.4;margin-bottom:6px;}}
    .law-meta{{display:flex;justify-content:space-between;align-items:center;}}
    .law-date{{font-size:0.74rem;color:var(--muted);font-family:'JetBrains Mono',monospace;}}
    .law-arrow{{font-size:0.76rem;color:var(--muted);transition:transform .2s;}}
    .law-item.expanded .law-arrow{{transform:rotate(180deg);}}
    .law-body{{
      display:none;padding:12px 14px 14px;border-top:1px solid var(--hairline);
    }}
    .law-item.expanded .law-body{{display:block;}}

    /* ── KEY POINTS ── */
    .section-label{{font-size:0.72rem;color:var(--muted);font-weight:600;margin:4px 0 6px;text-transform:uppercase;letter-spacing:.5px;}}
    .key-points{{list-style:none;margin-bottom:12px;}}
    .key-points li{{
      display:flex;gap:8px;padding:4px 0;
      font-size:0.83rem;color:var(--muted-strong);border-bottom:1px solid var(--hairline);
    }}
    .key-points li:last-child{{border-bottom:none;}}
    .kp-num{{color:var(--primary-text);font-weight:700;flex-shrink:0;min-width:16px;}}
    .kp-text{{flex:1;}}
    .raw-excerpt{{
      font-size:0.83rem;color:var(--muted-strong);line-height:1.7;margin-bottom:12px;
      white-space:pre-line;background:var(--surface);border:1px solid var(--hairline);
      border-radius:4px;padding:10px 12px;
    }}

    /* ── IMPACT ── */
    .impact-box{{
      font-size:0.81rem;color:var(--primary-text);
      background:rgba(252,213,53,.08);border-left:3px solid var(--primary);
      padding:8px 12px;border-radius:0 4px 4px 0;margin-bottom:12px;line-height:1.5;
    }}

    /* ── LAW FOOTER ── */
    .law-footer{{display:flex;gap:7px;flex-wrap:wrap;margin-top:4px;}}
    .btn-original{{
      background:rgba(252,213,53,.15);color:var(--primary-text);border:none;
      padding:5px 12px;border-radius:4px;font-size:0.78rem;cursor:pointer;
      text-decoration:none;display:inline-block;font-weight:600;
    }}
    .btn-original:hover{{filter:brightness(1.15);}}
    .btn-original-disabled{{
      color:var(--muted);font-size:0.78rem;padding:5px 12px;
      border:1px dashed var(--hairline);border-radius:4px;display:inline-block;
    }}
    .law-tag{{
      background:var(--surface);border:1px solid var(--hairline);color:var(--muted);
      padding:4px 10px;border-radius:4px;font-size:0.74rem;
      display:inline-flex;align-items:center;gap:4px;
    }}

    .no-items{{color:var(--muted);font-size:0.86rem;padding:16px 4px;}}

    .site-footer{{
      text-align:center;padding:20px;font-size:0.73rem;color:var(--muted);
      border-top:1px solid var(--hairline);margin-top:40px;
    }}
    @media(max-width:600px){{
      .kpi-row{{grid-template-columns:1fr 1fr;}}
      .cat-grid{{grid-template-columns:repeat(2,1fr);}}
      .week-range{{display:none;}}
      .header-right{{display:none;}}
      .card{{margin:0 12px 16px;}}
      .toolbar{{flex-wrap:wrap;}}
      /* 2026-08-20: 기존엔 .search-box의 flex:1(=flex-basis:0%)이 width:100%보다
         우선 적용돼 검색창이 옆 버튼과 한 줄에 끼어 좁아지는 버그가 있었음 —
         flex-basis를 100%로 명시해 항상 자기 줄 전체를 차지하도록 수정. */
      .search-box{{flex:1 1 100%;max-width:none;min-width:0;order:1;}}
      .toolbar-info{{order:0;}}
      /* 2026-08-20: "표시사항 변경 추적" 목록이 태그+제목+날짜를 한 줄에 욱여넣어
         좁은 화면에서 제목이 단어 중간까지 여러 줄로 쪼개지던 문제 — 태그·날짜를
         위쪽 한 줄로, 제목은 아래에 전체 너비로 분리. */
      .spotlight-item{{flex-wrap:wrap;row-gap:4px;}}
      .spotlight-item .tag{{order:0;}}
      .spotlight-meta{{order:1;}}
      .spotlight-title{{order:2;flex-basis:100%;}}
    }}
  </style>
</head>
<body>

<header class="site-header">
  <div class="header-left">
    <div class="header-titlerow">
      <h1>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
        식품 법령 개정 모니터
      </h1>
      <button class="theme-toggle" onclick="toggleTheme()" id="themeToggleBtn" title="라이트/다크 모드 전환"><span id="themeToggleIcon">🌙</span><span id="themeToggleLabel">라이트 모드</span></button>
    </div>
    <p>식약처 연동 · {years[-1] if years else ""}~{years[0] if years else ""}년 누적 아카이브</p>
  </div>
  <div class="header-right">
    <span class="hbadge">식약처</span>
    <span class="hbadge accent">총 {total_weeks}주차 · {all_items}건 수록</span>
  </div>
</header>

<div class="toolbar">
  <span class="toolbar-info">총 <b>{total_weeks}</b>주차 수록 · 누적 <b>{all_items}</b>건</span>
  <div class="search-box">
    <span class="search-icon">🔍</span>
    <input type="text" id="searchInput" class="search-input" placeholder="키워드 검색 (제목·내용)" oninput="setSearch(this.value)">
    <button class="search-clear" id="searchClearBtn" onclick="clearSearch()" hidden>✕</button>
  </div>
  <button class="btn-tool" onclick="expandAll()">모두 펼치기</button>
  <button class="btn-tool" onclick="collapseAll()">이전 주 접기</button>
  <button class="btn-tool btn-copy-all" onclick="copyAllArchive(this)">📋 전체 아카이브 복사</button>
</div>
<div class="filter-bar">
  <span id="yearFilterGroup" class="year-filter-group">
    <span class="filter-label">연도</span>
    <button class="filter-btn" onclick="setYear(this,'all')">전체</button>
    {year_btns_html}
    <div class="filter-sep"></div>
  </span>
  <span class="filter-label">상태</span>
  <button class="filter-btn active" onclick="setStatus(this,'all')">전체</button>
  <button class="filter-btn" onclick="setStatus(this,'시행')">시행</button>
  <button class="filter-btn" onclick="setStatus(this,'예고')">예고</button>
</div>
<div class="search-status" id="searchStatus" hidden></div>
<div class="main" id="searchResults" hidden></div>

<div id="normalView">
<div class="kpi-row">
  <div class="kpi">
    <div class="kpi-label">이번 주 수집</div>
    <div class="kpi-val">{kpi_total}<span class="kpi-unit">건</span></div>
  </div>
  <div class="kpi blue">
    <div class="kpi-label">시행 확정</div>
    <div class="kpi-val">{kpi_enforce}<span class="kpi-unit">건</span></div>
  </div>
  <div class="kpi orange">
    <div class="kpi-label">예고·검토</div>
    <div class="kpi-val">{kpi_notice}<span class="kpi-unit">건</span></div>
  </div>
  <div class="kpi red">
    <div class="kpi-label">누적 주차</div>
    <div class="kpi-val">{total_weeks}<span class="kpi-unit">주</span></div>
  </div>
</div>

{cat_overview_html}

{label_spotlight_html}

{monthly_summary_html}

<main class="main" id="weeksMain">
  {weeks_html}
</main>
</div>

<textarea id="archive-full-text" style="display:none">{esc(archive_text)}</textarea>

<footer class="site-footer">
  식품 법령 개정 모니터 · GitHub Actions 자동 수집 · 최종 업데이트 {esc(updated_str)}
</footer>

<script>
function applyThemeIcon() {{
  const isLight = document.documentElement.getAttribute('data-theme') === 'light';
  const icon = document.getElementById('themeToggleIcon');
  const label = document.getElementById('themeToggleLabel');
  if (icon) icon.textContent = isLight ? '☀️' : '🌙';
  if (label) label.textContent = isLight ? '다크 모드' : '라이트 모드';
}}
function toggleTheme() {{
  const cur = document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark';
  const next = cur === 'light' ? 'dark' : 'light';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('theme', next);
  applyThemeIcon();
}}
applyThemeIcon();

function toggleWeek(btn) {{
  btn.classList.toggle('open');
  btn.nextElementSibling.classList.toggle('open');
}}
function toggleItem(header) {{
  const item = header.closest('.law-item');
  if (item.classList.contains('expandable')) item.classList.toggle('expanded');
}}
function expandAll() {{
  document.querySelectorAll('.accordion-btn').forEach(b => {{
    b.classList.add('open');
    b.nextElementSibling.classList.add('open');
  }});
}}
function collapseAll() {{
  document.querySelectorAll('.accordion-btn:not(.open)').forEach(b => {{
    b.classList.add('open');b.nextElementSibling.classList.add('open');
  }});
  document.querySelectorAll('.accordion-btn.open:not(:first-of-type)').forEach(b => {{
    b.classList.remove('open');b.nextElementSibling.classList.remove('open');
  }});
}}

let activeYear='{default_year}', activeSt='all', activeCat='all', searchQuery='';
function applyFilter() {{
  // 검색 중이거나(카테고리 없이) 상태만 걸려있을 땐 결과가 흩어진 주차 전체를
  // 뒤져야 하므로 검색창 아래 평면 목록으로 전체 화면 전환. 유형(카테고리)이
  // 선택되면 대신 "유형별 현황" 카드 바로 아래에 드롭다운으로 펼쳐서 KPI·다른
  // 카드·주차 목록 등 나머지 화면은 그대로 유지한다(사용자 요청).
  const globalSwap = searchQuery !== '' || (activeCat === 'all' && activeSt !== 'all');
  document.getElementById('normalView').hidden = globalSwap;
  document.getElementById('searchResults').hidden = !globalSwap;
  document.getElementById('yearFilterGroup').hidden = globalSwap;
  const statusEl = document.getElementById('searchStatus');

  if (globalSwap) {{
    const matched = Array.from(document.querySelectorAll('#weeksMain .law-item')).filter(it => {{
      const stHide = activeSt!=='all' && it.dataset.status!==activeSt;
      const searchHide = searchQuery!=='' && !(it.dataset.search || '').includes(searchQuery);
      return !stHide && !searchHide;
    }});
    matched.sort((a, b) => (b.dataset.date || '').localeCompare(a.dataset.date || ''));

    const container = document.getElementById('searchResults');
    container.innerHTML = matched.length
      ? matched.map(it => {{
          const clone = it.cloneNode(true);
          clone.removeAttribute('id'); // 원본과 id 중복 방지 — 딥링크는 항상 #weeksMain의 원본을 가리킴
          clone.classList.remove('hidden');
          clone.classList.add('expanded');
          return clone.outerHTML;
        }}).join('')
      : '<p class="no-items" style="padding:24px 4px;">조건에 맞는 항목이 없습니다.</p>';

    const chips = [];
    if (searchQuery !== '') chips.push(`"${{searchQuery}}"`);
    if (activeSt !== 'all') chips.push(activeSt);
    const chipText = chips.length ? ' — ' + chips.map(c => `<b>${{c}}</b>`).join(' · ') : '';

    statusEl.hidden = false;
    statusEl.innerHTML = `<b>${{matched.length}}</b>건${{chipText}}` +
      `<button class="status-clear-btn" onclick="clearAllFilters()">✕ 필터 해제</button>`;
    return;
  }}

  statusEl.hidden = true;
  document.querySelectorAll('.week-section').forEach(w => {{
    w.classList.toggle('hidden', activeYear!=='all' && w.dataset.year!==activeYear);
  }});
  document.querySelectorAll('#weeksMain .law-item').forEach(it => it.classList.remove('hidden'));
  renderCatDropdown();
}}
function renderCatDropdown() {{
  const dropdown = document.getElementById('catDropdown');
  if (activeCat === 'all') {{
    dropdown.hidden = true;
    dropdown.innerHTML = '';
    return;
  }}
  const matched = Array.from(document.querySelectorAll('#weeksMain .law-item')).filter(it => {{
    const stHide = activeSt!=='all' && it.dataset.status!==activeSt;
    return it.dataset.category === activeCat && !stHide;
  }});
  matched.sort((a, b) => (b.dataset.date || '').localeCompare(a.dataset.date || ''));

  const statusChip = activeSt !== 'all' ? ` · <b>${{activeSt}}</b>` : '';
  const body = matched.length
    ? matched.map(it => {{
        const clone = it.cloneNode(true);
        clone.removeAttribute('id'); // 원본과 id 중복 방지
        clone.classList.remove('hidden');
        clone.classList.add('expanded');
        return clone.outerHTML;
      }}).join('')
    : '<p class="no-items" style="padding:8px 4px;">조건에 맞는 항목이 없습니다.</p>';

  dropdown.innerHTML = `<div class="cat-dropdown-status"><b>${{matched.length}}</b>건${{statusChip}}</div>` + body;
  dropdown.hidden = false;
}}
function clearAllFilters() {{
  document.getElementById('searchInput').value = '';
  searchQuery = '';
  document.getElementById('searchClearBtn').hidden = true;

  activeCat = 'all';
  document.querySelectorAll('[data-cat-btn]').forEach(b => b.classList.remove('active'));
  document.querySelector('[data-cat-btn][data-cat="all"]').classList.add('active');

  activeSt = 'all';
  document.querySelectorAll('.filter-btn[onclick*="setStatus"]').forEach(b => b.classList.remove('active'));
  document.querySelector(`.filter-btn[onclick="setStatus(this,'all')"]`).classList.add('active');

  applyFilter();
}}
function setSearch(val) {{
  searchQuery = val.trim().toLowerCase();
  document.getElementById('searchClearBtn').hidden = searchQuery === '';
  applyFilter();
}}
function clearSearch() {{
  document.getElementById('searchInput').value = '';
  setSearch('');
}}
function setYear(btn, val) {{
  document.querySelectorAll('.filter-btn[onclick*="setYear"]').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active'); activeYear=val; applyFilter();
}}
function setStatus(btn, val) {{
  document.querySelectorAll('.filter-btn[onclick*="setStatus"]').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active'); activeSt=val; applyFilter();
}}
function setCategory(btn, val) {{
  // 이미 선택된 카드를 다시 누르면 드롭다운을 닫는다(토글).
  activeCat = (activeCat === val && val !== 'all') ? 'all' : val;
  document.querySelectorAll('[data-cat-btn]').forEach(b => b.classList.remove('active'));
  document.querySelector(`[data-cat-btn][data-cat="${{activeCat}}"]`).classList.add('active');
  applyFilter();
}}
applyFilter();

function handleDeepLink() {{
  // health-trend "오늘의 요약"의 법령 항목 클릭 등 #law-xxxxx 해시로 들어왔을 때,
  // 연도 필터·접힌 아코디언에 가려 있어도 그 항목까지 자동으로 펼쳐서 보여준다.
  const hash = location.hash.slice(1);
  if (!hash) return;
  const el = document.getElementById(hash);
  if (!el || !el.classList.contains('law-item')) return;

  if (activeYear !== 'all') {{
    activeYear = 'all';
    document.querySelectorAll('.filter-btn[onclick*="setYear"]').forEach(b => b.classList.remove('active'));
    document.querySelector(`.filter-btn[onclick="setYear(this,'all')"]`).classList.add('active');
    applyFilter();
  }}

  const weekSection = el.closest('.week-section');
  if (weekSection) {{
    const btn = weekSection.querySelector('.accordion-btn');
    const content = weekSection.querySelector('.week-content');
    if (btn && !btn.classList.contains('open')) {{
      btn.classList.add('open');
      content.classList.add('open');
    }}
  }}
  if (el.classList.contains('expandable')) el.classList.add('expanded');

  setTimeout(() => {{
    el.scrollIntoView({{behavior: 'smooth', block: 'center'}});
    el.classList.add('deep-link-highlight');
    setTimeout(() => el.classList.remove('deep-link-highlight'), 2000);
  }}, 80);
}}
handleDeepLink();

async function copyText(btn, text) {{
  try {{
    await navigator.clipboard.writeText(text);
    btn.textContent='✓ 복사됨'; btn.classList.add('copied');
    setTimeout(()=>{{ btn.textContent='요약 복사'; btn.classList.remove('copied'); }}, 1800);
  }} catch(e) {{}}
}}

async function copyAllArchive(btn) {{
  const text = document.getElementById('archive-full-text').value;
  const original = btn.textContent;
  try {{
    await navigator.clipboard.writeText(text);
    btn.textContent='✓ 전체 복사됨';
    setTimeout(()=>{{ btn.textContent=original; }}, 1800);
  }} catch(e) {{}}
}}
</script>
</body>
</html>"""

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"사이트 빌드 완료: {OUTPUT_PATH}")


if __name__ == "__main__":
    build()
