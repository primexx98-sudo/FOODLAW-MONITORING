"""data/archive.json을 읽어 docs/index.html을 생성합니다."""

import json
import os
import re
from datetime import datetime

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
    """AI 요약이 아직 없는 항목(대부분 2023~2025년 백로그, 하루 10건 제한으로 순차
    처리 중)도 상세페이지에서 이미 수집해둔 실제 본문(body_text)이 있으면 그걸
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
    return f"""
    <div class="law-footer">
      <a class="btn-original" href="{esc(source_url)}" target="_blank" rel="noopener">원문 바로가기</a>
      {"".join(tags)}
    </div>"""


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

    return f"""
<div class="law-item {expandable}" data-source="{esc(source)}" data-status="{esc(status)}">
  <div class="law-header" onclick="toggleItem(this)">
    <div class="law-tags">
      <span class="tag {st_cls}">{esc(status)}</span>
      <span class="tag {src_cls}">{esc(source)}</span>
      <span class="tag tag-official">공식</span>
      {interest_badge}
      {new_badge}
    </div>
    <div class="law-title">{title}</div>
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

    return f"""
<div class="week-section" data-year="{esc(year)}">
  <button class="accordion-btn {btn_open}" onclick="toggleWeek(this)">
    <div class="week-left">
      <span class="week-num">{esc(year)}년 {esc(week_num)}주차</span>
      <span class="week-range">{esc(start).replace("-", ".")} ~ {esc(end)[5:].replace("-", ".")}</span>
    </div>
    <div class="week-right">
      {"<span class='badge-latest'>최신</span>" if is_latest else "<span class='badge-prev'>이전</span>"}
      <span class="week-count">{total}건</span>
      <span class="week-arrow">{"▴" if is_latest else "▾"}</span>
    </div>
  </button>
  <div class="week-content {open_cls}">
    {"<div class='summary-box'><div class='summary-title'>✦ 이번 주 통합 요약 (" + esc(summary_date) + ")" + "</div><p class='summary-text'>" + esc(weekly_summary) + "</p>" + copy_btn + "</div>" if weekly_summary else ""}
    <div class="groups-wrap">
      {groups_html}
    </div>
  </div>
</div>"""


def build():
    if not os.path.exists(ARCHIVE_PATH):
        weeks, total_weeks, last_updated = [], 0, ""
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
    all_items = sum(len(w.get("items", [])) for w in weeks)

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

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>식품 법령 개정 모니터</title>
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
    :root{{
      --bg:#1a1d1b;--bg2:#1f2320;--surface:#252926;--surface2:#2c302e;
      --border:#343834;--border2:#3d413b;
      --text:#dde8df;--sub:#8a9e8e;
      --green:#52b788;--green2:#2d6a4f;--green3:#b7e4c7;
      --blue:#4db6e8;--orange:#e8a838;--red:#d95f5f;--red2:#f28b82;
    }}
    :root[data-theme="light"]{{
      --bg:#f6f8f6;--bg2:#eef1ee;--surface:#ffffff;--surface2:#eef1ee;
      --border:#dde3dd;--border2:#c9d1c9;
      --text:#1a2320;--sub:#5c6b60;
      --green:#2d8659;--green2:#d7f0e2;--green3:#1f5c3d;
      --blue:#1f7aa8;--orange:#a86a1a;--red:#c0392b;--red2:#9c2b1f;
    }}
    body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Apple SD Gothic Neo','Noto Sans KR',sans-serif;
      background:var(--bg);color:var(--text);font-size:14px;line-height:1.65;}}

    /* ── HEADER ── */
    /* 헤더는 라이트/다크 상관없이 항상 고정 다크 그린 그라디언트라, 안의 텍스트 색도
       전역 테마 변수(var(--sub) 등)를 쓰면 라이트 모드에서 배경과 같은 톤이 되어
       안 보이는 문제가 생김 — 헤더 내부는 고정값 사용 */
    .site-header{{
      background:linear-gradient(135deg,#0d2016 0%,#1a3a27 100%);
      border-bottom:1px solid var(--border);
      padding:14px 24px 12px;
      display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:10px;
    }}
    .header-left{{display:flex;flex-direction:column;gap:2px;}}
    .header-left h1{{font-size:1.15rem;font-weight:700;color:#b7e4c7;letter-spacing:-.3px;}}
    .header-left h1 svg{{vertical-align:middle;margin-right:6px;}}
    .header-left p{{font-size:0.75rem;color:rgba(255,255,255,.55);margin-top:3px;}}
    .header-titlerow{{display:flex;align-items:center;gap:8px;}}
    .header-right{{display:flex;gap:6px;flex-wrap:wrap;align-items:center;}}
    .hbadge{{background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,.15);
      border-radius:4px;padding:3px 9px;font-size:0.72rem;color:rgba(255,255,255,.7);}}
    .hbadge.green{{background:#2d6a4f;color:#b7e4c7;border-color:#52b788;}}
    .theme-toggle{{
      background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.2);
      color:#b7e4c7;width:26px;height:26px;border-radius:50%;cursor:pointer;
      display:inline-flex;align-items:center;justify-content:center;font-size:0.85rem;
      flex-shrink:0;line-height:1;
    }}
    .theme-toggle:hover{{background:rgba(255,255,255,.15);}}

    /* ── TOOLBAR ── */
    .toolbar{{
      background:var(--bg2);border-bottom:1px solid var(--border);
      padding:7px 24px;display:flex;align-items:center;gap:8px;flex-wrap:wrap;
    }}
    .toolbar-info{{font-size:0.8rem;color:var(--sub);flex:1;}}
    .toolbar-info b{{color:var(--green);}}
    .btn-tool{{
      background:var(--surface);border:1px solid var(--border2);color:var(--text);
      padding:4px 11px;border-radius:4px;font-size:0.78rem;cursor:pointer;
    }}
    .btn-tool:hover{{background:var(--green2);color:var(--green3);}}

    /* ── FILTER ── */
    .filter-bar{{
      background:var(--bg2);border-bottom:1px solid var(--border);
      padding:7px 24px;display:flex;gap:6px;flex-wrap:wrap;align-items:center;
    }}
    .filter-label{{font-size:0.74rem;color:var(--sub);}}
    .filter-sep{{width:1px;height:14px;background:var(--border2);margin:0 4px;}}
    .filter-btn{{
      background:transparent;border:1px solid var(--border2);color:var(--sub);
      padding:3px 11px;border-radius:20px;font-size:0.75rem;cursor:pointer;
    }}
    .filter-btn.active{{background:var(--green2);border-color:var(--green);color:var(--green3);}}

    /* ── KPI ── */
    .kpi-row{{
      display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));
      gap:8px;padding:14px 24px;background:var(--bg2);border-bottom:1px solid var(--border);
    }}
    .kpi{{background:var(--surface);border:1px solid var(--border);border-radius:7px;
      padding:12px 15px;border-left:3px solid var(--green);}}
    .kpi.blue{{border-left-color:var(--blue);}}
    .kpi.orange{{border-left-color:var(--orange);}}
    .kpi.red{{border-left-color:var(--red);}}
    .kpi-label{{font-size:0.72rem;color:var(--sub);margin-bottom:4px;}}
    .kpi-val{{font-size:1.35rem;font-weight:700;}}
    .kpi-unit{{font-size:0.7rem;color:var(--sub);}}

    /* ── MAIN ── */
    .main{{max-width:860px;margin:0 auto;padding:14px 20px 80px;}}

    /* ── WEEK ── */
    .week-section{{
      background:var(--surface);border:1px solid var(--border);
      border-radius:8px;margin-bottom:10px;overflow:hidden;
    }}
    .week-section.hidden{{display:none;}}
    .accordion-btn{{
      width:100%;background:none;border:none;padding:12px 18px;
      display:flex;justify-content:space-between;align-items:center;cursor:pointer;color:var(--text);
    }}
    .accordion-btn:hover{{background:rgba(255,255,255,0.025);}}
    .week-left{{display:flex;align-items:center;gap:14px;}}
    .week-num{{font-size:1rem;font-weight:700;color:var(--green);}}
    .week-range{{font-size:0.8rem;color:var(--sub);}}
    .week-right{{display:flex;align-items:center;gap:7px;}}
    .badge-latest{{background:var(--red);color:#fff;font-size:0.68rem;font-weight:700;padding:2px 6px;border-radius:3px;}}
    .badge-prev{{background:var(--surface2);color:var(--sub);font-size:0.68rem;padding:2px 6px;border-radius:3px;}}
    .week-count{{background:var(--green2);color:var(--green3);font-size:0.75rem;font-weight:600;padding:2px 8px;border-radius:4px;}}
    .week-arrow{{font-size:0.8rem;color:var(--sub);transition:transform .2s;}}
    .accordion-btn.open .week-arrow{{transform:rotate(180deg);}}
    .week-content{{display:none;border-top:1px solid var(--border);}}
    .week-content.open{{display:block;}}

    /* ── SUMMARY BOX ── */
    .summary-box{{
      background:rgba(45,106,79,0.12);border-bottom:1px solid var(--border);
      padding:14px 18px;
    }}
    .summary-title{{font-size:0.78rem;color:var(--green);font-weight:600;margin-bottom:7px;}}
    .summary-text{{font-size:0.83rem;color:var(--sub);line-height:1.7;}}
    .btn-copy{{
      display:inline-flex;align-items:center;gap:5px;
      margin-top:10px;background:var(--surface2);border:1px solid var(--border2);
      color:var(--sub);padding:4px 11px;border-radius:4px;font-size:0.75rem;cursor:pointer;
    }}
    .btn-copy:hover{{background:var(--green2);color:var(--green3);}}
    .btn-copy.copied{{color:var(--green);border-color:var(--green);}}

    /* ── GROUPS ── */
    .groups-wrap{{padding:10px 14px 14px;}}
    .group-section{{margin-bottom:12px;}}
    .group-header{{
      display:flex;align-items:center;gap:8px;
      padding:6px 0;margin-bottom:6px;
      border-bottom:1px dashed var(--border);
    }}
    .group-dot{{width:8px;height:8px;border-radius:50%;flex-shrink:0;}}
    .dot-enforce{{background:var(--green);}}
    .dot-notice{{background:var(--orange);}}
    .dot-other{{background:var(--sub);}}
    .group-label{{font-size:0.77rem;color:var(--sub);flex:1;}}
    .group-count{{font-size:0.74rem;color:var(--sub);}}

    /* ── LAW ITEM ── */
    .law-item{{
      background:var(--bg2);border:1px solid var(--border);
      border-radius:6px;margin-bottom:7px;overflow:hidden;
    }}
    .law-item.hidden{{display:none;}}
    .law-header{{padding:11px 14px;cursor:pointer;}}
    .law-item.expandable .law-header:hover{{background:rgba(255,255,255,0.02);}}
    .law-tags{{display:flex;gap:5px;flex-wrap:wrap;align-items:center;margin-bottom:6px;}}
    .tag{{display:inline-block;padding:2px 7px;border-radius:3px;font-size:0.7rem;font-weight:600;}}
    .tag-green{{background:rgba(82,183,136,.15);color:var(--green);border:1px solid rgba(82,183,136,.3);}}
    .tag-blue{{background:rgba(77,182,232,.15);color:var(--blue);border:1px solid rgba(77,182,232,.3);}}
    .tag-orange{{background:rgba(232,168,56,.15);color:var(--orange);border:1px solid rgba(232,168,56,.3);}}
    .tag-gray{{background:rgba(255,255,255,.07);color:var(--sub);border:1px solid var(--border);}}
    .tag-official{{background:rgba(255,255,255,.05);color:var(--sub);border:1px solid var(--border);}}
    .tag-interest{{background:rgba(217,95,95,.15);color:var(--red2);border:1px solid rgba(217,95,95,.35);}}
    .status-enforce{{background:rgba(82,183,136,.2);color:#6edb9e;border:1px solid rgba(82,183,136,.4);}}
    .status-notice{{background:rgba(232,168,56,.2);color:#f0c060;border:1px solid rgba(232,168,56,.4);}}
    .status-pub{{background:rgba(77,182,232,.2);color:#7dd4f5;border:1px solid rgba(77,182,232,.4);}}
    /* 밝은 파스텔 텍스트는 다크 배경 전용 — 라이트 모드에서는 흰 바탕에 대비가 안 나와서 진한 색으로 교체 */
    :root[data-theme="light"] .status-enforce{{color:#1f7a52;}}
    :root[data-theme="light"] .status-notice{{color:#8a5a10;}}
    :root[data-theme="light"] .status-pub{{color:#1565a0;}}
    .status-info{{background:rgba(255,255,255,.07);color:var(--sub);border:1px solid var(--border);}}
    .badge-new{{background:var(--red);color:#fff;font-size:0.66rem;font-weight:700;padding:2px 5px;border-radius:3px;}}
    .law-title{{font-size:0.88rem;font-weight:600;line-height:1.45;margin-bottom:5px;}}
    .law-meta{{display:flex;justify-content:space-between;align-items:center;}}
    .law-date{{font-size:0.74rem;color:var(--sub);}}
    .law-arrow{{font-size:0.76rem;color:var(--sub);transition:transform .2s;}}
    .law-item.expanded .law-arrow{{transform:rotate(180deg);}}
    .law-body{{
      display:none;padding:12px 14px 14px;border-top:1px solid var(--border);
    }}
    .law-item.expanded .law-body{{display:block;}}

    /* ── KEY POINTS ── */
    .section-label{{font-size:0.72rem;color:var(--sub);font-weight:600;margin:4px 0 6px;text-transform:uppercase;letter-spacing:.5px;}}
    .key-points{{list-style:none;margin-bottom:12px;}}
    .key-points li{{
      display:flex;gap:8px;padding:4px 0;
      font-size:0.83rem;color:var(--sub);border-bottom:1px solid var(--border);
    }}
    .key-points li:last-child{{border-bottom:none;}}
    .kp-num{{color:var(--green);font-weight:700;flex-shrink:0;min-width:16px;}}
    .kp-text{{flex:1;}}
    .raw-excerpt{{
      font-size:0.83rem;color:var(--sub);line-height:1.7;margin-bottom:12px;
      white-space:pre-line;background:var(--bg2);border:1px solid var(--border);
      border-radius:4px;padding:10px 12px;
    }}

    /* ── IMPACT ── */
    .impact-box{{
      font-size:0.81rem;color:var(--orange);
      background:rgba(232,168,56,.08);border-left:3px solid var(--orange);
      padding:8px 12px;border-radius:0 4px 4px 0;margin-bottom:12px;line-height:1.5;
    }}

    /* ── LAW FOOTER ── */
    .law-footer{{display:flex;gap:7px;flex-wrap:wrap;margin-top:4px;}}
    .btn-original{{
      background:var(--green2);color:var(--green3);border:none;
      padding:5px 12px;border-radius:4px;font-size:0.78rem;cursor:pointer;
      text-decoration:none;display:inline-block;
    }}
    .btn-original:hover{{filter:brightness(1.15);}}
    .law-btn{{
      background:var(--surface2);border:1px solid var(--border2);color:var(--sub);
      padding:4px 10px;border-radius:4px;font-size:0.74rem;text-decoration:none;
      display:inline-flex;align-items:center;gap:4px;
    }}
    .law-btn:hover{{background:var(--surface);color:var(--text);}}
    .law-tag{{
      background:var(--surface2);border:1px solid var(--border2);color:var(--sub);
      padding:4px 10px;border-radius:4px;font-size:0.74rem;
      display:inline-flex;align-items:center;gap:4px;
    }}

    .no-items{{color:var(--sub);font-size:0.86rem;padding:16px 4px;}}

    .site-footer{{
      text-align:center;padding:20px;font-size:0.73rem;color:var(--sub);
      border-top:1px solid var(--border);margin-top:40px;
    }}
    @media(max-width:600px){{
      .kpi-row{{grid-template-columns:1fr 1fr;}}
      .week-range{{display:none;}}
      .header-right{{display:none;}}
    }}
  </style>
</head>
<body>

<header class="site-header">
  <div class="header-left">
    <div class="header-titlerow">
      <h1>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color:#52b788"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
        식품 법령 개정 모니터
      </h1>
      <button class="theme-toggle" onclick="toggleTheme()" id="themeToggleBtn" title="라이트/다크 모드 전환">🌙</button>
    </div>
    <p>고메베이글 개발팀 · 식약처 연동 · {years[-1] if years else ""}~{years[0] if years else ""}년 누적 아카이브</p>
  </div>
  <div class="header-right">
    <span class="hbadge">식약처</span>
    <span class="hbadge green">총 {total_weeks}주차 · {all_items}건 수록</span>
  </div>
</header>

<div class="toolbar">
  <span class="toolbar-info">총 <b>{total_weeks}</b>주차 수록 · 누적 <b>{all_items}</b>건</span>
  <button class="btn-tool" onclick="expandAll()">모두 펼치기</button>
  <button class="btn-tool" onclick="collapseAll()">이전 주 접기</button>
  <button class="btn-tool btn-copy-all" onclick="copyAllArchive(this)">📋 전체 아카이브 복사</button>
</div>

<div class="filter-bar">
  <span class="filter-label">연도</span>
  <button class="filter-btn" onclick="setYear(this,'all')">전체</button>
  {year_btns_html}
  <div class="filter-sep"></div>
  <span class="filter-label">상태</span>
  <button class="filter-btn active" onclick="setStatus(this,'all')">전체</button>
  <button class="filter-btn" onclick="setStatus(this,'시행')">시행</button>
  <button class="filter-btn" onclick="setStatus(this,'예고')">예고</button>
</div>

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

<main class="main">
  {weeks_html}
</main>

<textarea id="archive-full-text" style="display:none">{esc(archive_text)}</textarea>

<footer class="site-footer">
  식품 법령 개정 모니터 · GitHub Actions 자동 수집 · 최종 업데이트 {esc(updated_str)}
</footer>

<script>
function applyThemeIcon() {{
  const isLight = document.documentElement.getAttribute('data-theme') === 'light';
  const btn = document.getElementById('themeToggleBtn');
  if (btn) btn.textContent = isLight ? '☀️' : '🌙';
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

let activeYear='{default_year}', activeSt='all';
function applyFilter() {{
  document.querySelectorAll('.week-section').forEach(w => {{
    w.classList.toggle('hidden', activeYear!=='all' && w.dataset.year!==activeYear);
  }});
  document.querySelectorAll('.law-item').forEach(it => {{
    it.classList.toggle('hidden', activeSt!=='all' && it.dataset.status!==activeSt);
  }});
}}
function setYear(btn, val) {{
  document.querySelectorAll('.filter-btn[onclick*="setYear"]').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active'); activeYear=val; applyFilter();
}}
function setStatus(btn, val) {{
  document.querySelectorAll('.filter-btn[onclick*="setStatus"]').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active'); activeSt=val; applyFilter();
}}
applyFilter();

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
