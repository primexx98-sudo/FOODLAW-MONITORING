"""data/statute_library.json → docs/statute/index.html 렌더링.

시각적 일관성을 위해 build_site.py(법령 모니터)와 동일한 색상 토큰·폰트·사이드바
셸·검색 패턴(#normalView/#searchResults 클론-후-평면목록)을 재사용한다. 법령 모니터는
"매주 새로 쌓이는 뉴스형 피드"라 연도별 지연로딩·주차 아코디언이 필요했지만, 여기는
법령 수가 고정(~20개)이라 그런 장치 없이 전부 한 번에 렌더링한다.
"""

import html
import json
import os
from datetime import datetime, timezone

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "statute_library.json")
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "docs", "statute", "index.html")

TARGET_LABELS = {"law": "법령", "admrul": "고시"}

CATEGORY_ORDER = ["표시광고", "건기식", "포장재", "원산지", "식품첨가물", "이력추적"]
CATEGORY_COLORS = {
    "표시광고": "#5046e5", "건기식": "#0a9f68", "포장재": "#2563eb",
    "원산지": "#d97706", "식품첨가물": "#0f8f88", "이력추적": "#d63447",
}


def esc(s: str) -> str:
    return html.escape(s or "", quote=True)


def fmt_date(raw: str) -> str:
    if raw and len(raw) == 8:
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"
    return raw or "-"


def build_search_text(statute: dict) -> str:
    cur = statute["current"]
    parts = [statute["name"], statute["category"]]
    for a in cur.get("articles", []):
        parts.append(a.get("title", ""))
    body = " ".join(a.get("text", "") for a in cur.get("articles", []))
    parts.append(body[:800])
    return esc(" ".join(parts).lower())


def render_diff_line(line: dict) -> str:
    cls = "diff-added" if line["type"] == "added" else "diff-removed"
    return f'<div class="{cls}">{esc(line["text"])}</div>'


def render_history(statute: dict) -> str:
    history = statute.get("history", [])
    if not history:
        return ""
    entries = []
    for h in history:
        changes_html = []
        for c in h["changes"]:
            if c["change_type"] == "modified":
                lines_html = "".join(render_diff_line(l) for l in c.get("diff_lines", []))
                changes_html.append(f'''
                  <div class="change-item change-modified">
                    <div class="change-head">제{esc(c["article_no"])}조{f"({esc(c['title'])})" if c["title"] else ""} <span class="change-tag">개정</span></div>
                    <div class="change-diff">{lines_html}</div>
                  </div>''')
            elif c["change_type"] == "added":
                changes_html.append(f'''
                  <div class="change-item change-added">
                    <div class="change-head">제{esc(c["article_no"])}조{f"({esc(c['title'])})" if c["title"] else ""} <span class="change-tag">신설</span></div>
                    <div class="change-diff"><div class="diff-added">{esc(c["new_text"])}</div></div>
                  </div>''')
            else:
                changes_html.append(f'''
                  <div class="change-item change-removed">
                    <div class="change-head">제{esc(c["article_no"])}조{f"({esc(c['title'])})" if c["title"] else ""} <span class="change-tag">삭제</span></div>
                    <div class="change-diff"><div class="diff-removed">{esc(c["old_text"])}</div></div>
                  </div>''')
        entries.append(f'''
          <details class="history-entry">
            <summary>{fmt_date(h["effective_date"])} 시행본 → 개정 (조문 {len(h["changes"])}건 변경, 감지일 {h["detected_at"][:10]})</summary>
            <div class="history-changes">{"".join(changes_html)}</div>
          </details>''')
    return f'''
      <div class="statute-history">
        <div class="statute-history-label">개정 이력 ({len(history)}건)</div>
        {"".join(entries)}
      </div>'''


def render_articles(statute: dict) -> str:
    cur = statute["current"]
    if not statute["text_available"]:
        return f'''
          <div class="statute-no-text">
            이 항목은 국가법령정보 Open API가 본문 텍스트를 제공하지 않습니다(방대한 별표·서식 위주 고시).
            <a href="{esc(cur["detail_url"])}" target="_blank" rel="noopener">국가법령정보센터에서 원문 보기 →</a>
          </div>'''
    articles = cur.get("articles", [])
    items = []
    for a in articles:
        label = f'제{esc(a["no"])}조' if a["no"] else ""
        title = f'({esc(a["title"])})' if a["title"] else ""
        items.append(f'''
          <details class="article-item">
            <summary>{label}{title if label else esc(a["title"]) or "전문"}</summary>
            <div class="article-text">{esc(a["text"])}</div>
          </details>''')
    return f'<div class="statute-articles">{"".join(items)}</div>'


def render_statute(statute: dict) -> str:
    cur = statute["current"]
    target_label = TARGET_LABELS.get(statute["api_target"], statute["api_target"])
    cat = statute["category"]
    cat_color = CATEGORY_COLORS.get(cat, "#8695ab")
    changed_badge = '<span class="badge-changed">개정 반영</span>' if statute.get("history") else ""
    search_text = build_search_text(statute)

    return f'''
    <div class="statute-item" id="statute-{esc(statute["key"])}" data-search="{search_text}" data-category="{esc(cat)}">
      <div class="statute-header">
        <span class="statute-cat-dot" style="background:{cat_color}"></span>
        <span class="statute-target-badge">{target_label}</span>
        <h3 class="statute-name">{esc(statute["name"])}</h3>
        {changed_badge}
      </div>
      <div class="statute-meta">
        시행일자 {fmt_date(cur["effective_date"])} · 공포일자 {fmt_date(cur["promulgation_date"])}
        {f' · 발령·공포번호 {esc(cur["promulgation_no"])}' if cur.get("promulgation_no") else ""}
        · <a href="{esc(cur["detail_url"])}" target="_blank" rel="noopener">원문 링크</a>
      </div>
      {render_articles(statute)}
      {render_history(statute)}
    </div>'''


def build():
    with open(DATA_PATH, encoding="utf-8") as f:
        library = json.load(f)

    statutes = library["statutes"]
    by_cat = {}
    for s in statutes:
        by_cat.setdefault(s["category"], []).append(s)

    cats_present = [c for c in CATEGORY_ORDER if c in by_cat]
    cats_present += [c for c in by_cat if c not in CATEGORY_ORDER]

    nav_items = "".join(
        f'<button class="nav-item" data-cat="{esc(c)}" onclick="setCategory(\'{esc(c)}\')">'
        f'<span><span class="statute-cat-dot" style="background:{CATEGORY_COLORS.get(c, "#8695ab")}"></span> {esc(c)}</span>'
        f'<span class="nav-item-count">{len(by_cat[c])}</span></button>'
        for c in cats_present
    )

    items_html = "".join(render_statute(s) for s in statutes)
    changed_count = sum(1 for s in statutes if s.get("history"))
    generated = library.get("generated_at", datetime.now(timezone.utc).isoformat())

    html_out = f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>법령자료</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">
  <script>
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
      --canvas:#ffffff;--surface:#f6f7fb;--surface-elevated:#eef0f7;
      --hairline:#e3e8ee;--body-text:#0d253d;--muted:#8695ab;--muted-strong:#425466;
      --primary:#5046e5;--primary-text:#5046e5;--primary-active:#3f37c9;
      --up:#0a9f68;--down:#d63447;--info:#2563eb;--turquoise:#0f8f88;
    }}
    :root[data-theme="dark"]{{
      --canvas:#0b0e14;--surface:#161a22;--surface-elevated:#1f2430;
      --hairline:#262c38;--body-text:#eef1f7;--muted:#7c8494;--muted-strong:#b9c0cf;
      --primary:#7c74f5;--primary-text:#7c74f5;--primary-active:#948dfd;
      --up:#0ecb81;--down:#f6465d;--info:#3b82f6;--turquoise:#2dbdb6;
    }}
    body{{font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI','Apple SD Gothic Neo','Noto Sans KR',sans-serif;
      background:var(--canvas);color:var(--body-text);font-size:14px;line-height:1.65;}}
    .mono{{font-family:'JetBrains Mono',monospace;}}

    .shell{{display:flex;align-items:flex-start;min-height:100vh;}}
    .sidebar{{width:216px;flex-shrink:0;background:var(--surface);border-right:1px solid var(--hairline);
      padding:20px 14px;position:sticky;top:0;height:100vh;overflow-y:auto;}}
    .sidebar-brand{{display:flex;align-items:center;justify-content:space-between;margin-bottom:4px;padding:0 6px;}}
    .sidebar-brand h1{{font-size:0.98rem;font-weight:700;color:var(--body-text);letter-spacing:-.2px;}}
    .sidebar-sub{{font-size:0.7rem;color:var(--muted);padding:0 6px;margin-bottom:20px;line-height:1.5;}}
    .theme-toggle{{background:var(--surface-elevated);border:1px solid var(--hairline);
      color:var(--body-text);width:26px;height:26px;border-radius:13px;cursor:pointer;
      display:inline-flex;align-items:center;justify-content:center;flex-shrink:0;font-size:0.8rem;}}
    .theme-toggle:hover{{background:var(--hairline);}}
    .nav-group-label{{font-size:0.68rem;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;font-weight:600;padding:0 8px;margin-bottom:5px;}}
    .nav-item{{display:flex;align-items:center;justify-content:space-between;width:100%;text-align:left;
      background:none;border:none;padding:8px 8px;border-radius:6px;font-size:0.8rem;color:var(--muted-strong);
      cursor:pointer;font-family:inherit;min-height:34px;gap:6px;}}
    .nav-item:hover{{background:var(--surface-elevated);}}
    .nav-item.active{{background:rgba(80,70,229,.1);color:var(--primary-text);font-weight:700;}}
    .nav-item-count{{font-family:'JetBrains Mono',monospace;font-size:0.7rem;color:var(--muted);flex-shrink:0;}}

    .main-col{{flex:1;min-width:0;}}
    .toolbar{{background:var(--canvas);border-bottom:1px solid var(--hairline);
      padding:14px 24px;display:flex;align-items:center;gap:8px;flex-wrap:wrap;}}
    .search-box{{display:flex;align-items:center;gap:6px;background:var(--surface-elevated);
      border:1px solid var(--hairline);border-radius:8px;padding:0 10px;height:32px;
      flex:1 1 100%;max-width:320px;min-width:160px;}}
    .search-icon{{font-size:0.8rem;opacity:0.7;flex-shrink:0;}}
    .search-input{{background:transparent;border:none;outline:none;color:var(--body-text);
      font-size:0.82rem;font-family:'Inter',sans-serif;flex:1;min-width:0;}}
    .search-input::placeholder{{color:var(--muted);}}
    .search-status{{padding:6px 24px;font-size:0.78rem;color:var(--muted);background:var(--canvas);
      border-bottom:1px solid var(--hairline);display:flex;align-items:center;gap:10px;flex-wrap:wrap;}}
    .search-status b{{color:var(--primary-text);}}
    .search-status[hidden]{{display:none;}}
    .status-clear-btn{{background:none;border:1px solid var(--hairline);color:var(--muted);
      padding:2px 9px;border-radius:20px;font-size:0.72rem;cursor:pointer;}}
    .status-clear-btn:hover{{background:var(--surface-elevated);color:var(--body-text);}}

    .stat-strip{{display:flex;align-items:center;gap:14px;flex-wrap:wrap;font-size:0.8rem;color:var(--muted-strong);
      padding:16px 24px;border-bottom:1px solid var(--hairline);}}
    .stat-strip b{{font-family:'JetBrains Mono',monospace;font-size:0.95rem;color:var(--body-text);font-weight:700;}}

    .main{{max-width:820px;margin:16px auto;padding:0 24px 60px;}}
    #normalView[hidden], #searchResults[hidden]{{display:none;}}

    .statute-item{{background:var(--surface);border-radius:12px;padding:16px 18px;margin-bottom:14px;}}
    .statute-header{{display:flex;align-items:center;gap:8px;flex-wrap:wrap;}}
    .statute-cat-dot{{width:8px;height:8px;border-radius:50%;flex-shrink:0;}}
    .statute-target-badge{{font-size:0.68rem;font-weight:700;color:var(--primary-text);
      background:rgba(80,70,229,.1);border-radius:4px;padding:2px 6px;}}
    .statute-name{{font-size:0.95rem;font-weight:700;flex:1;min-width:0;}}
    .badge-changed{{font-size:0.68rem;font-weight:700;color:var(--down);
      background:rgba(214,52,71,.1);border-radius:4px;padding:2px 6px;}}
    .statute-meta{{font-size:0.76rem;color:var(--muted);margin-top:6px;}}
    .statute-meta a{{color:var(--primary-text);text-decoration:none;}}
    .statute-meta a:hover{{text-decoration:underline;}}

    .statute-articles{{margin-top:10px;border-top:1px solid var(--hairline);padding-top:6px;}}
    .article-item{{border-bottom:1px solid var(--hairline);}}
    .article-item:last-child{{border-bottom:none;}}
    .article-item summary{{padding:7px 2px;font-size:0.83rem;cursor:pointer;color:var(--body-text);}}
    .article-item summary:hover{{color:var(--primary-text);}}
    .article-text{{font-size:0.82rem;color:var(--muted-strong);line-height:1.7;padding:0 2px 10px 14px;white-space:pre-wrap;}}
    .statute-no-text{{margin-top:10px;font-size:0.82rem;color:var(--muted-strong);
      background:var(--surface-elevated);border-radius:8px;padding:10px 12px;}}
    .statute-no-text a{{color:var(--primary-text);text-decoration:none;}}

    .statute-history{{margin-top:12px;border-top:1px solid var(--hairline);padding-top:8px;}}
    .statute-history-label{{font-size:0.72rem;font-weight:700;color:var(--down);text-transform:uppercase;letter-spacing:.04em;margin-bottom:4px;}}
    .history-entry summary{{padding:6px 2px;font-size:0.8rem;cursor:pointer;color:var(--muted-strong);}}
    .history-entry summary:hover{{color:var(--body-text);}}
    .history-changes{{padding-left:12px;}}
    .change-item{{margin:8px 0;padding:8px 10px;border-radius:8px;background:var(--surface-elevated);}}
    .change-head{{font-size:0.78rem;font-weight:700;margin-bottom:6px;}}
    .change-tag{{font-size:0.66rem;font-weight:700;padding:1px 6px;border-radius:4px;margin-left:4px;}}
    .change-modified .change-tag{{background:rgba(37,99,235,.12);color:var(--info);}}
    .change-added .change-tag{{background:rgba(10,159,104,.12);color:var(--up);}}
    .change-removed .change-tag{{background:rgba(214,52,71,.12);color:var(--down);}}
    .change-diff{{font-size:0.8rem;line-height:1.6;}}
    .diff-added{{background:rgba(10,159,104,.12);color:var(--body-text);padding:2px 6px;border-radius:4px;margin:2px 0;}}
    .diff-removed{{background:rgba(214,52,71,.12);color:var(--muted-strong);text-decoration:line-through;padding:2px 6px;border-radius:4px;margin:2px 0;}}

    @media(max-width:760px){{
      .shell{{flex-direction:column;}}
      .sidebar{{width:100%;height:auto;position:static;display:flex;overflow-x:auto;gap:4px;padding:10px;}}
      .sidebar-sub{{display:none;}}
    }}
  </style>
</head>
<body>
<div class="shell">
  <aside class="sidebar">
    <div class="sidebar-brand">
      <h1>📜 법령자료</h1>
      <button class="theme-toggle" onclick="toggleTheme()">🌓</button>
    </div>
    <div class="sidebar-sub">실무 참조용 법령·고시 {len(statutes)}종의 최신 원문과<br>개정 시 조문 단위 변경사항을 추적합니다.</div>
    <div class="nav-group-label">카테고리</div>
    <button class="nav-item active" data-cat="all" onclick="setCategory('all')">
      <span>전체</span><span class="nav-item-count">{len(statutes)}</span>
    </button>
    {nav_items}
  </aside>
  <div class="main-col">
    <div class="toolbar">
      <div class="search-box">
        <span class="search-icon">🔍</span>
        <input class="search-input" type="text" placeholder="법령명·조문 내용 검색" oninput="setSearch(this.value)">
      </div>
    </div>
    <div class="search-status" id="searchStatus" hidden></div>
    <div class="stat-strip">
      총 <b>{len(statutes)}</b>개 법령·고시 추적 중 <span class="mono">·</span>
      최근 개정 감지 <b>{changed_count}</b>건 <span class="mono">·</span>
      최종 갱신 {generated[:16].replace('T', ' ')} UTC
    </div>
    <div id="normalView">
      <main class="main" id="itemsMain">
        {items_html}
      </main>
    </div>
    <div class="main" id="searchResults" hidden></div>
  </div>
</div>
<script>
  function toggleTheme() {{
    var cur = document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
    var next = cur === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('theme', next);
  }}

  var searchQuery = '';
  var activeCat = 'all';

  function setSearch(v) {{
    searchQuery = (v || '').trim().toLowerCase();
    applyFilter();
  }}

  function setCategory(cat) {{
    activeCat = (activeCat === cat) ? 'all' : cat;
    document.querySelectorAll('.nav-item').forEach(function(b) {{
      b.classList.toggle('active', b.dataset.cat === activeCat || (activeCat === 'all' && b.dataset.cat === 'all'));
    }});
    applyFilter();
  }}

  function applyFilter() {{
    var filtering = searchQuery !== '' || activeCat !== 'all';
    var normalView = document.getElementById('normalView');
    var results = document.getElementById('searchResults');
    var status = document.getElementById('searchStatus');

    if (!filtering) {{
      normalView.hidden = false;
      results.hidden = true;
      status.hidden = true;
      return;
    }}

    var items = Array.prototype.slice.call(document.querySelectorAll('#itemsMain .statute-item'));
    var matched = items.filter(function(it) {{
      var textOk = !searchQuery || (it.dataset.search || '').includes(searchQuery);
      var catOk = activeCat === 'all' || it.dataset.category === activeCat;
      return textOk && catOk;
    }});

    results.innerHTML = '';
    matched.forEach(function(it) {{
      var clone = it.cloneNode(true);
      clone.removeAttribute('id');
      results.appendChild(clone);
    }});

    normalView.hidden = true;
    results.hidden = false;
    status.hidden = false;
    var chips = [];
    if (searchQuery) chips.push('검색어 "' + searchQuery + '"');
    if (activeCat !== 'all') chips.push('카테고리 "' + activeCat + '"');
    status.innerHTML = '<b>' + matched.length + '</b>건 검색됨 (' + chips.join(', ') + ')' +
      '<button class="status-clear-btn" onclick="clearAllFilters()">✕ 필터 해제</button>';
  }}

  function clearAllFilters() {{
    searchQuery = '';
    activeCat = 'all';
    document.querySelector('.search-input').value = '';
    document.querySelectorAll('.nav-item').forEach(function(b) {{
      b.classList.toggle('active', b.dataset.cat === 'all');
    }});
    applyFilter();
  }}
</script>
</body>
</html>"""

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(html_out)
    print(f"법령자료 사이트 생성 완료: {OUT_PATH} ({len(statutes)}건)")


if __name__ == "__main__":
    build()
