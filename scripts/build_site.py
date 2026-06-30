"""data/archive.json을 읽어 docs/index.html을 생성합니다.

실행 방법:
  python scripts/build_site.py
"""

import json
import os
from datetime import datetime

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
ARCHIVE_PATH = os.path.join(REPO_ROOT, "data", "archive.json")
OUTPUT_PATH = os.path.join(REPO_ROOT, "docs", "index.html")

SOURCE_COLORS = {
    "법제처": ("tag-blue", "📜"),
    "식약처": ("tag-green", "🏛"),
    "식품안전나라": ("tag-orange", "🍱"),
}
STATUS_COLORS = {
    "시행": "status-enforce",
    "예고": "status-notice",
    "공포": "status-pub",
    "공고": "status-pub",
    "공지": "status-info",
}


def esc(text):
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def render_item(item, index):
    title = esc(item.get("title", ""))
    source = item.get("source", "")
    status = item.get("status", "")
    date = esc(item.get("date", ""))
    url = esc(item.get("url", "#"))
    key_points = item.get("key_points", [])
    impact = esc(item.get("industry_impact", ""))
    is_new = item.get("is_new", False)

    src_cls, src_icon = SOURCE_COLORS.get(source, ("tag-gray", "📄"))
    st_cls = STATUS_COLORS.get(status, "status-info")

    new_badge = '<span class="badge-new">NEW</span>' if is_new else ""
    points_html = ""
    if key_points:
        points_html = "<ul class='key-points'>" + "".join(
            f"<li>{esc(p)}</li>" for p in key_points
        ) + "</ul>"
    impact_html = f"<p class='impact'>💡 업계 영향 — {impact}</p>" if impact else ""

    return f"""
    <div class="law-item" data-source="{esc(source)}" data-status="{esc(status)}">
      <div class="law-header" onclick="toggleItem(this)">
        <div class="law-tags">
          <span class="tag {src_cls}">{src_icon} {esc(source)}</span>
          <span class="tag {st_cls}">{esc(status)}</span>
          {new_badge}
        </div>
        <div class="law-title">{title}</div>
        <div class="law-meta">
          <span class="law-date">📅 {date}</span>
          <span class="law-arrow">▼</span>
        </div>
      </div>
      <div class="law-body">
        {points_html}
        {impact_html}
        <a class="law-link" href="{url}" target="_blank" rel="noopener">원문 바로가기 →</a>
      </div>
    </div>"""


def render_week(week, index):
    week_num = week.get("week_num", index + 1)
    year = week.get("year", "")
    start = week.get("start_date", "")
    end = week.get("end_date", "")
    summary = esc(week.get("summary", ""))
    items = week.get("items", [])
    counts = week.get("counts", {})
    total = counts.get("total", len(items))
    label = esc(week.get("label", f"{week_num}주차"))

    is_latest = index == 0
    open_cls = "open" if is_latest else ""
    btn_cls = "accordion-btn open" if is_latest else "accordion-btn"

    items_html = "".join(render_item(item, i) for i, item in enumerate(items))
    if not items_html:
        items_html = '<p class="no-items">이번 주 수집된 항목이 없습니다.</p>'

    enforce_cnt = counts.get("시행", 0)
    notice_cnt = counts.get("예고", 0)

    return f"""
  <div class="week-section">
    <button class="{btn_cls}" onclick="toggleWeek(this)">
      <div class="week-left">
        <span class="week-label">{label}</span>
        <span class="week-range">{esc(start)} ~ {esc(end)}</span>
      </div>
      <div class="week-right">
        {"<span class='badge-latest'>최신</span>" if is_latest else ""}
        <span class="week-count">{total}건</span>
        <span class="week-arrow">{"▲" if is_latest else "▼"}</span>
      </div>
    </button>
    <div class="week-content {open_cls}">
      <div class="week-summary">
        <div class="summary-icon">📋</div>
        <div class="summary-text">
          <strong>이번 주 통합 요약</strong>
          <p>{summary}</p>
          <div class="summary-mini">
            <span>시행 <b>{enforce_cnt}</b>건</span>
            <span>예고 <b>{notice_cnt}</b>건</span>
          </div>
        </div>
      </div>
      <div class="items-list">
        {items_html}
      </div>
    </div>
  </div>"""


def build():
    if not os.path.exists(ARCHIVE_PATH):
        print("archive.json이 없습니다. collect_all.py를 먼저 실행하세요.")
        weeks = []
        total_weeks = 0
        last_updated = ""
    else:
        with open(ARCHIVE_PATH, "r", encoding="utf-8") as f:
            archive = json.load(f)
        weeks = archive.get("weeks", [])
        total_weeks = archive.get("total_weeks", len(weeks))
        last_updated = archive.get("last_updated", "")

    # 최신 주 KPI
    latest = weeks[0] if weeks else {}
    latest_counts = latest.get("counts", {})
    kpi_total = latest_counts.get("total", 0)
    kpi_enforce = latest_counts.get("시행", 0)
    kpi_notice = latest_counts.get("예고", 0)

    if last_updated:
        try:
            dt = datetime.fromisoformat(last_updated)
            updated_str = dt.strftime("%Y.%m.%d %H:%M")
        except Exception:
            updated_str = last_updated
    else:
        updated_str = datetime.now().strftime("%Y.%m.%d %H:%M")

    weeks_html = "".join(render_week(w, i) for i, w in enumerate(weeks))
    if not weeks_html:
        weeks_html = '<p class="no-items" style="padding:40px;text-align:center;">아직 수집된 데이터가 없습니다.<br>GitHub Actions를 실행하면 자동으로 채워집니다.</p>'

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>식품 법령 개정 모니터</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    :root {{
      --primary: #1a3a2a;
      --primary-mid: #2d6a4f;
      --primary-light: #40916c;
      --bg: #1c1f1e;
      --bg2: #242827;
      --surface: #2a2e2c;
      --border: #363b38;
      --text: #e8ede9;
      --text-sub: #9aab9e;
      --green: #52b788;
      --blue: #4fc3f7;
      --orange: #ffb74d;
      --red: #ef5350;
    }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Apple SD Gothic Neo', 'Noto Sans KR', sans-serif;
      background: var(--bg);
      color: var(--text);
      font-size: 14px;
      line-height: 1.6;
    }}

    /* Header */
    .site-header {{
      background: var(--primary);
      border-bottom: 1px solid var(--border);
      padding: 16px 20px 12px;
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .header-title h1 {{ font-size: 1.2rem; font-weight: 700; color: #b7e4c7; }}
    .header-title p {{ font-size: 0.78rem; color: var(--text-sub); margin-top: 2px; }}
    .header-badges {{ display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }}
    .hbadge {{
      background: rgba(255,255,255,0.08);
      border: 1px solid var(--border);
      border-radius: 4px;
      padding: 3px 8px;
      font-size: 0.74rem;
      color: var(--text-sub);
    }}
    .hbadge.accent {{ background: var(--primary-mid); color: #b7e4c7; border-color: var(--primary-light); }}

    /* Toolbar */
    .toolbar {{
      background: var(--bg2);
      border-bottom: 1px solid var(--border);
      padding: 8px 20px;
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
    }}
    .toolbar-info {{ font-size: 0.82rem; color: var(--text-sub); flex: 1; }}
    .toolbar-info b {{ color: var(--green); }}
    .btn-tool {{
      background: var(--surface);
      border: 1px solid var(--border);
      color: var(--text);
      padding: 5px 12px;
      border-radius: 4px;
      font-size: 0.8rem;
      cursor: pointer;
      transition: background 0.15s;
    }}
    .btn-tool:hover {{ background: var(--primary-mid); color: #b7e4c7; }}

    /* Filter bar */
    .filter-bar {{
      background: var(--bg2);
      border-bottom: 1px solid var(--border);
      padding: 8px 20px;
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      align-items: center;
    }}
    .filter-label {{ font-size: 0.78rem; color: var(--text-sub); margin-right: 4px; }}
    .filter-btn {{
      background: var(--surface);
      border: 1px solid var(--border);
      color: var(--text-sub);
      padding: 4px 12px;
      border-radius: 20px;
      font-size: 0.78rem;
      cursor: pointer;
      transition: all 0.15s;
    }}
    .filter-btn.active {{
      background: var(--primary-mid);
      border-color: var(--green);
      color: #b7e4c7;
    }}

    /* KPI cards */
    .kpi-row {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      gap: 10px;
      padding: 16px 20px;
      background: var(--bg2);
      border-bottom: 1px solid var(--border);
    }}
    .kpi-card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 14px 16px;
      border-left: 3px solid var(--green);
    }}
    .kpi-card.blue {{ border-left-color: var(--blue); }}
    .kpi-card.orange {{ border-left-color: var(--orange); }}
    .kpi-card.red {{ border-left-color: var(--red); }}
    .kpi-label {{ font-size: 0.74rem; color: var(--text-sub); margin-bottom: 4px; }}
    .kpi-value {{ font-size: 1.3rem; font-weight: 700; color: var(--text); }}
    .kpi-sub {{ font-size: 0.72rem; color: var(--text-sub); margin-top: 2px; }}

    /* Main */
    .main {{ max-width: 900px; margin: 0 auto; padding: 16px 20px 60px; }}

    /* Week section */
    .week-section {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 8px;
      margin-bottom: 12px;
      overflow: hidden;
    }}
    .accordion-btn {{
      width: 100%;
      background: none;
      border: none;
      padding: 14px 18px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      cursor: pointer;
      color: var(--text);
      gap: 12px;
    }}
    .accordion-btn:hover {{ background: rgba(255,255,255,0.03); }}
    .week-left {{ display: flex; align-items: center; gap: 12px; flex: 1; }}
    .week-label {{ font-size: 0.88rem; font-weight: 700; color: var(--green); }}
    .week-range {{ font-size: 0.82rem; color: var(--text-sub); }}
    .week-right {{ display: flex; align-items: center; gap: 8px; }}
    .week-count {{
      background: var(--primary-mid);
      color: #b7e4c7;
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 0.78rem;
      font-weight: 600;
    }}
    .week-arrow {{ font-size: 0.74rem; color: var(--text-sub); transition: transform 0.2s; }}
    .accordion-btn.open .week-arrow {{ transform: rotate(180deg); }}
    .badge-latest {{
      background: var(--red);
      color: white;
      font-size: 0.7rem;
      font-weight: 700;
      padding: 2px 6px;
      border-radius: 3px;
    }}

    .week-content {{ display: none; border-top: 1px solid var(--border); }}
    .week-content.open {{ display: block; }}

    /* Summary box */
    .week-summary {{
      background: rgba(45,106,79,0.15);
      border-bottom: 1px solid var(--border);
      padding: 14px 18px;
      display: flex;
      gap: 12px;
      align-items: flex-start;
    }}
    .summary-icon {{ font-size: 1.2rem; flex-shrink: 0; }}
    .summary-text strong {{ font-size: 0.82rem; color: var(--green); display: block; margin-bottom: 4px; }}
    .summary-text p {{ font-size: 0.83rem; color: var(--text-sub); line-height: 1.6; }}
    .summary-mini {{ margin-top: 8px; display: flex; gap: 16px; font-size: 0.8rem; color: var(--text-sub); }}
    .summary-mini b {{ color: var(--text); }}

    /* Law item */
    .items-list {{ padding: 10px 14px; }}
    .law-item {{
      background: var(--bg2);
      border: 1px solid var(--border);
      border-radius: 6px;
      margin-bottom: 8px;
      overflow: hidden;
    }}
    .law-item.hidden {{ display: none; }}
    .law-header {{
      padding: 12px 14px;
      cursor: pointer;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }}
    .law-header:hover {{ background: rgba(255,255,255,0.02); }}
    .law-tags {{ display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }}
    .tag {{
      display: inline-block;
      padding: 2px 8px;
      border-radius: 3px;
      font-size: 0.72rem;
      font-weight: 600;
    }}
    .tag-green {{ background: rgba(82,183,136,0.15); color: var(--green); border: 1px solid rgba(82,183,136,0.3); }}
    .tag-blue {{ background: rgba(79,195,247,0.15); color: var(--blue); border: 1px solid rgba(79,195,247,0.3); }}
    .tag-orange {{ background: rgba(255,183,77,0.15); color: var(--orange); border: 1px solid rgba(255,183,77,0.3); }}
    .tag-gray {{ background: rgba(255,255,255,0.08); color: var(--text-sub); border: 1px solid var(--border); }}
    .status-enforce {{ background: rgba(82,183,136,0.2); color: #69d4a0; border: 1px solid rgba(82,183,136,0.4); }}
    .status-notice {{ background: rgba(255,183,77,0.2); color: #ffd082; border: 1px solid rgba(255,183,77,0.4); }}
    .status-pub {{ background: rgba(79,195,247,0.2); color: #7dd8fa; border: 1px solid rgba(79,195,247,0.4); }}
    .status-info {{ background: rgba(255,255,255,0.08); color: var(--text-sub); border: 1px solid var(--border); }}
    .badge-new {{
      background: var(--red);
      color: white;
      font-size: 0.68rem;
      font-weight: 700;
      padding: 2px 6px;
      border-radius: 3px;
    }}
    .law-title {{ font-size: 0.9rem; font-weight: 600; color: var(--text); line-height: 1.4; }}
    .law-meta {{ display: flex; justify-content: space-between; align-items: center; }}
    .law-date {{ font-size: 0.76rem; color: var(--text-sub); }}
    .law-arrow {{ font-size: 0.7rem; color: var(--text-sub); transition: transform 0.2s; }}
    .law-item.expanded .law-arrow {{ transform: rotate(180deg); }}

    .law-body {{
      display: none;
      padding: 0 14px 14px;
      border-top: 1px solid var(--border);
    }}
    .law-item.expanded .law-body {{ display: block; }}
    .key-points {{
      list-style: none;
      margin: 12px 0;
    }}
    .key-points li {{
      padding: 4px 0 4px 16px;
      position: relative;
      font-size: 0.84rem;
      color: var(--text-sub);
    }}
    .key-points li::before {{
      content: "①②③④⑤⑥⑦⑧⑨⑩";
      position: absolute;
      left: 0;
      color: var(--green);
      font-size: 0.78rem;
    }}
    .impact {{
      font-size: 0.82rem;
      color: var(--orange);
      background: rgba(255,183,77,0.08);
      border-left: 3px solid var(--orange);
      padding: 8px 12px;
      margin: 10px 0;
      border-radius: 0 4px 4px 0;
    }}
    .law-link {{
      display: inline-block;
      margin-top: 10px;
      font-size: 0.8rem;
      color: var(--blue);
      text-decoration: none;
    }}
    .law-link:hover {{ text-decoration: underline; }}

    .no-items {{ color: var(--text-sub); font-size: 0.88rem; padding: 20px 18px; }}

    /* Footer */
    .site-footer {{
      text-align: center;
      padding: 20px;
      font-size: 0.76rem;
      color: var(--text-sub);
      border-top: 1px solid var(--border);
      margin-top: 40px;
    }}

    @media (max-width: 600px) {{
      .kpi-row {{ grid-template-columns: 1fr 1fr; }}
      .week-range {{ display: none; }}
      .site-header {{ flex-direction: column; }}
    }}
  </style>
</head>
<body>

<header class="site-header">
  <div class="header-title">
    <h1>⚖️ 식품 법령 개정 모니터</h1>
    <p>식약처 · 법제처 · 식품안전나라 연동 · 주간 누적 아카이브</p>
  </div>
  <div class="header-badges">
    <span class="hbadge">최종 업데이트 {esc(updated_str)}</span>
    <span class="hbadge">식약처</span>
    <span class="hbadge">법제처</span>
    <span class="hbadge">식품안전나라</span>
    <span class="hbadge accent">총 {total_weeks}주차 수록</span>
  </div>
</header>

<div class="toolbar">
  <span class="toolbar-info">총 <b>{total_weeks}</b>주차 수록</span>
  <button class="btn-tool" onclick="expandAll()">모두 펼치기</button>
  <button class="btn-tool" onclick="collapseAll()">모두 접기</button>
</div>

<div class="filter-bar">
  <span class="filter-label">출처</span>
  <button class="filter-btn active" onclick="filterItems(this, 'all')">전체</button>
  <button class="filter-btn" onclick="filterItems(this, '법제처')">법제처</button>
  <button class="filter-btn" onclick="filterItems(this, '식약처')">식약처</button>
  <button class="filter-btn" onclick="filterItems(this, '식품안전나라')">식품안전나라</button>
  <span class="filter-label" style="margin-left:8px;">상태</span>
  <button class="filter-btn active" onclick="filterStatus(this, 'all')">전체</button>
  <button class="filter-btn" onclick="filterStatus(this, '시행')">시행</button>
  <button class="filter-btn" onclick="filterStatus(this, '예고')">예고</button>
</div>

<div class="kpi-row">
  <div class="kpi-card">
    <div class="kpi-label">이번 주 수집</div>
    <div class="kpi-value">{kpi_total}</div>
    <div class="kpi-sub">건</div>
  </div>
  <div class="kpi-card blue">
    <div class="kpi-label">시행 중</div>
    <div class="kpi-value">{kpi_enforce}</div>
    <div class="kpi-sub">건</div>
  </div>
  <div class="kpi-card orange">
    <div class="kpi-label">예고·검토 중</div>
    <div class="kpi-value">{kpi_notice}</div>
    <div class="kpi-sub">건</div>
  </div>
  <div class="kpi-card red">
    <div class="kpi-label">총 누적 주차</div>
    <div class="kpi-value">{total_weeks}</div>
    <div class="kpi-sub">주차</div>
  </div>
</div>

<main class="main">
  {weeks_html}
</main>

<footer class="site-footer">
  <p>식품 법령 개정 모니터 · GitHub Actions 자동 수집 · 최종 업데이트: {esc(updated_str)}</p>
</footer>

<script>
  function toggleWeek(btn) {{
    btn.classList.toggle('open');
    btn.nextElementSibling.classList.toggle('open');
    const arrow = btn.querySelector('.week-arrow');
    if (arrow) arrow.textContent = btn.classList.contains('open') ? '▲' : '▼';
  }}

  function toggleItem(header) {{
    const item = header.closest('.law-item');
    item.classList.toggle('expanded');
  }}

  function expandAll() {{
    document.querySelectorAll('.accordion-btn').forEach(btn => {{
      btn.classList.add('open');
      btn.nextElementSibling.classList.add('open');
      const arrow = btn.querySelector('.week-arrow');
      if (arrow) arrow.textContent = '▲';
    }});
  }}

  function collapseAll() {{
    document.querySelectorAll('.accordion-btn').forEach(btn => {{
      btn.classList.remove('open');
      btn.nextElementSibling.classList.remove('open');
      const arrow = btn.querySelector('.week-arrow');
      if (arrow) arrow.textContent = '▼';
    }});
  }}

  let activeSource = 'all';
  let activeStatus = 'all';

  function applyFilter() {{
    document.querySelectorAll('.law-item').forEach(item => {{
      const src = item.dataset.source || '';
      const st = item.dataset.status || '';
      const srcOk = activeSource === 'all' || src === activeSource;
      const stOk = activeStatus === 'all' || st === activeStatus;
      item.classList.toggle('hidden', !(srcOk && stOk));
    }});
  }}

  function filterItems(btn, value) {{
    document.querySelectorAll('.filter-bar .filter-btn').forEach(b => {{
      if (['all','법제처','식약처','식품안전나라'].includes(b.textContent.trim()) ||
          b.textContent.trim() === '전체') {{
        if (['all','법제처','식약처','식품안전나라'].includes(value)) b.classList.remove('active');
      }}
    }});
    btn.classList.add('active');
    activeSource = value;
    applyFilter();
  }}

  function filterStatus(btn, value) {{
    document.querySelectorAll('.filter-bar .filter-btn').forEach(b => {{
      if (['all','시행','예고'].includes(b.textContent.trim())) b.classList.remove('active');
    }});
    btn.classList.add('active');
    activeStatus = value;
    applyFilter();
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
