"""data/statute_library.json → docs/statute/index.html 렌더링.

시각적 일관성을 위해 build_site.py(법령 모니터)와 동일한 색상 토큰·폰트·사이드바
셸·검색 패턴(#normalView/#searchResults 클론-후-평면목록)을 재사용한다. 법령 모니터는
"매주 새로 쌓이는 뉴스형 피드"라 연도별 지연로딩·주차 아코디언이 필요했지만, 여기는
법령 수가 고정(~20개)이라 그런 장치 없이 전부 한 번에 렌더링한다.
"""

import html
import json
import os
import re
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


# law.go.kr이 조문 본문을 "다음 각호와 같다.1. 일반사항가. ~2. 제품명" 식으로 항목 사이
# 줄바꿈 없이 통짜로 준다 — 실측(건강기능식품의 표시기준 제5조)으로 가독성 문제 확인.
# 숫자 항목("1." "2.")과 괄호 항목("1)" "2)")은 뒤에 바로 한글이 오는 패턴이 문장 중간
# 소수점(예: "0.15밀리그램")·조문 참조("제1항")와 겹치지 않아 안전하게 줄바꿈 삽입 가능.
# 가/나/다/라 같은 한글 항목 기호는 "다."(평서문 종결) 등과 구분이 안 돼(예: "~한다."가
# 매 문장 끝에 나옴) 잘못 끊길 위험이 커서 이번 스코프에서는 건드리지 않음 — "가."만
# 예외적으로 처리(문장 종결어미로는 거의 안 쓰여 상대적으로 안전).
_NUM_ITEM_RE = re.compile(r"(\d{1,3}\.)(?=\s?[가-힣「(])")
_PAREN_ITEM_RE = re.compile(r"(\d{1,3}\))(?=\s?[가-힣])")
_GA_ITEM_RE = re.compile(r"(가\.)(?=\s?[가-힣「(])")


def format_legal_text(text: str) -> str:
    text = _NUM_ITEM_RE.sub(r"\n\1", text)
    text = _PAREN_ITEM_RE.sub(r"\n\1", text)
    text = _GA_ITEM_RE.sub(r"\n\1", text)
    return text.strip()


def build_search_text(statute: dict) -> str:
    """data-search 속성엔 이름·카테고리만 담는다 — 조문·별표 전문은 이미 카드 안
    `<details>`(접혀 있어도 DOM엔 존재)에 그대로 있어서 JS가 `textContent`로 바로
    읽으면 되므로, 여기서 또 복제해 담을 필요가 없다. 처음엔 조문 800자·별표 전체를
    이 속성에도 중복 저장했는데, 800자 캡 때문에 "건강기능식품"처럼 별표 후반부에
    있는 검색어가 인덱스에서 잘려나가는 문제가 실측으로 발견됨 — 캡을 늘리는 대신
    아예 중복 저장을 없애 캡 자체를 무의미하게 만듦(파일 크기 절감 효과도 있음)."""
    return esc(f"{statute['name']} {statute['category']}".lower())


def render_diff_line(line: dict) -> str:
    cls = "diff-added" if line["type"] == "added" else "diff-removed"
    return f'<div class="{cls}">{esc(line["text"])}</div>'


def render_change_item(c: dict, kind: str) -> str:
    if kind == "annex":
        # 별표 식별자(별표키, 예: "000100")는 사람이 읽기엔 의미 없으니 제목만 보여줌
        label = "별표"
        title = f' · {esc(c["title"])}' if c.get("title") else ""
    else:
        label = f'제{esc(c["article_no"])}조' if c["article_no"] else "전문"
        title = f'({esc(c["title"])})' if c.get("title") else ""
    if c["change_type"] == "modified":
        lines_html = "".join(render_diff_line(l) for l in c.get("diff_lines", []))
        return f'''
          <div class="change-item change-modified">
            <div class="change-head">{label}{title} <span class="change-tag">개정</span></div>
            <div class="change-diff">{lines_html}</div>
          </div>'''
    if c["change_type"] == "added":
        return f'''
          <div class="change-item change-added">
            <div class="change-head">{label}{title} <span class="change-tag">신설</span></div>
            <div class="change-diff"><div class="diff-added">{esc(c["new_text"])}</div></div>
          </div>'''
    return f'''
      <div class="change-item change-removed">
        <div class="change-head">{label}{title} <span class="change-tag">삭제</span></div>
        <div class="change-diff"><div class="diff-removed">{esc(c["old_text"])}</div></div>
      </div>'''


def render_history(statute: dict) -> str:
    history = statute.get("history", [])
    if not history:
        return ""
    entries = []
    for h in history:
        article_changes = h.get("article_changes", [])
        annex_changes = h.get("annex_changes", [])
        changes_html = "".join(render_change_item(c, "article") for c in article_changes)
        annex_html = "".join(render_change_item(c, "annex") for c in annex_changes)
        entries.append(f'''
          <details class="history-entry">
            <summary>{fmt_date(h["effective_date"])} 시행본 → 개정 (조문 {len(article_changes)}건 · 별표 {len(annex_changes)}건 변경, 감지일 {h["detected_at"][:10]})</summary>
            <div class="history-changes">{changes_html}{annex_html}</div>
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
          <details class="article-item" data-kind="article" data-no="{esc(a["no"])}">
            <summary>{label}{title if label else esc(a["title"]) or "전문"}</summary>
            <div class="article-text">{esc(format_legal_text(a["text"]))}</div>
          </details>''')
    return f'<div class="statute-articles">{"".join(items)}</div>'


def render_annexes(statute: dict) -> str:
    """별표(표 형식 첨부) — 조문 본문엔 없고 별표에만 있는 정보(예: 원산지 표시대상
    품목)가 실제로 존재해서 조문과 별개로 노출한다. 박스 그리기 문자로 된 표라 고정폭
    폰트(.mono)가 아니면 정렬이 깨짐."""
    annexes = statute["current"].get("annexes", [])
    if not annexes:
        return ""
    items = []
    for a in annexes:
        items.append(f'''
          <details class="article-item" data-kind="annex" data-no="{esc(a["no"])}">
            <summary>{esc(a["title"]) or "별표"}</summary>
            <pre class="annex-text mono">{esc(a["text"])}</pre>
          </details>''')
    return f'''
      <div class="statute-annexes">
        <div class="statute-annexes-label">별표·서식 ({len(annexes)}건)</div>
        {"".join(items)}
      </div>'''


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
      {render_annexes(statute)}
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

    .btn-tool{{background:var(--surface-elevated);border:1px solid var(--hairline);color:var(--body-text);
      padding:7px 12px;border-radius:8px;font-size:0.78rem;cursor:pointer;white-space:nowrap;}}
    .btn-tool:hover{{background:var(--hairline);}}
    .btn-tool.active{{background:rgba(80,70,229,.14);border-color:var(--primary);color:var(--primary-text);font-weight:700;}}
    .ai-status{{padding:6px 24px;font-size:0.78rem;color:var(--primary-text);background:var(--canvas);
      border-bottom:1px solid var(--hairline);}}
    .ai-status[hidden]{{display:none;}}
    .ai-results{{padding:10px 24px;background:var(--surface);border-bottom:1px solid var(--hairline);}}
    .ai-results[hidden]{{display:none;}}
    .ai-results-label{{font-size:0.72rem;font-weight:700;color:var(--primary-text);text-transform:uppercase;
      letter-spacing:.04em;margin-bottom:6px;}}
    .ai-result-item{{display:block;width:100%;text-align:left;background:var(--surface-elevated);
      border:1px solid var(--hairline);border-radius:8px;padding:8px 10px;margin-bottom:6px;
      cursor:pointer;font-family:inherit;color:var(--body-text);font-size:0.82rem;}}
    .ai-result-item:hover{{border-color:var(--primary);}}
    .ai-result-score{{color:var(--muted);font-size:0.72rem;font-family:'JetBrains Mono',monospace;margin-left:6px;}}
    @keyframes pulseHighlight{{0%,100%{{background:transparent;}}50%{{background:rgba(80,70,229,.18);}}}}
    .deep-link-highlight{{animation:pulseHighlight 1s ease-in-out 2;}}
    /* 검색 결과에서 실제로 검색어와 일치한 조문/별표를 자동으로 펼치고 표시 —
       법령만 좁혀주고 그 안의 항목은 일일이 찾아보게 하지 않기 위함. */
    .article-item.search-hit{{border-left:3px solid var(--primary);background:rgba(80,70,229,.06);}}
    .article-item.search-hit summary{{font-weight:700;color:var(--primary-text);}}

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

    .statute-annexes{{margin-top:10px;border-top:1px solid var(--hairline);padding-top:6px;}}
    .statute-annexes-label{{font-size:0.72rem;font-weight:700;color:var(--turquoise);text-transform:uppercase;letter-spacing:.04em;margin-bottom:2px;}}
    .annex-text{{font-size:0.74rem;color:var(--muted-strong);line-height:1.5;padding:6px 2px 10px 14px;white-space:pre;overflow-x:auto;}}

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
      <button class="btn-tool" id="aiToggleBtn" onclick="toggleAiMode()">🧠 AI 의미검색</button>
    </div>
    <div class="ai-status" id="aiStatus" hidden></div>
    <div class="ai-results" id="aiResults" hidden></div>
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
    scheduleAiSearch();
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

    // 단어 단위 AND 매칭: "원산지 표시대상"처럼 띄어쓰기나 어순이 실제 조문 표현과
    // 달라도(예: "원산지의 표시대상") 각 단어가 본문 어딘가에 있기만 하면 찾도록 함 —
    // 이전엔 입력어 전체를 연속 문자열로 그대로 대조해서 이런 경우를 못 찾았음.
    var searchTokens = searchQuery.split(/\s+/).filter(Boolean);
    // 조문·별표 전문은 data-search에 없음 — 접혀있는 <details>도 DOM엔 그대로 있으므로
    // textContent가 전체 본문을 캡 없이 그대로 돌려준다(자세한 이유는 build_search_text 참고).
    var items = Array.prototype.slice.call(document.querySelectorAll('#itemsMain .statute-item'));
    var matched = [];
    items.forEach(function(it) {{
      var catOk = activeCat === 'all' || it.dataset.category === activeCat;
      if (!catOk) return;
      // 법령 하나에 조문·별표가 수십 개씩 있어서, 어느 법령인지만 좁혀주면 그 안에서
      // 또 일일이 펼쳐봐야 함(실제 사용자 피드백) — 어느 조문/별표가 검색어와
      // *직접* 일치하는지 여기서 미리 찾아서, 그 항목만 자동으로 펼쳐서 보여준다.
      var directHits = [];
      if (searchTokens.length) {{
        it.querySelectorAll('.article-item').forEach(function(sub) {{
          var subText = sub.textContent.toLowerCase();
          if (searchTokens.every(function(tok) {{ return subText.includes(tok); }})) {{
            directHits.push(sub);
          }}
        }});
      }}
      var wholeText = ((it.dataset.search || '') + ' ' + it.textContent).toLowerCase();
      var textOk = !searchTokens.length || directHits.length > 0 ||
        searchTokens.every(function(tok) {{ return wholeText.includes(tok); }});
      if (!textOk) return;
      // 방대한 공전류 조문 하나(수만 자)가 우연히 단어를 다 포함하는 경우와, 그 주제만
      // 다루는 짧고 정확한 별표/조문을 구분하기 위해 가장 짧은(=가장 구체적인) 일치
      // 항목의 글자수를 함께 기록 — 정렬 시 "얼마나 정확히 그 얘기만 하는 항목인지"의
      // 대리 지표로 쓴다(실측: 방대한 고시의 통짜 조문이 관련 별표보다 먼저 뜨는 문제 발견).
      var minLen = directHits.length
        ? Math.min.apply(null, directHits.map(function(h) {{ return h.textContent.length; }}))
        : Infinity;
      matched.push({{
        el: it, hitCount: directHits.length, minLen: minLen,
        hitNos: directHits.map(function(h) {{ return h.dataset.kind + ':' + h.dataset.no; }}),
      }});
    }});
    // 1) 조문·별표 단위로 직접 일치한 법령을 이름 등으로만 걸린 법령보다 먼저,
    // 2) 그 안에서도 가장 짧고 구체적인(=핵심만 다루는) 일치 항목을 가진 법령을 먼저.
    matched.sort(function(a, b) {{
      if (a.hitCount !== b.hitCount) return b.hitCount - a.hitCount;
      if (a.minLen === Infinity && b.minLen === Infinity) return 0; // 둘 다 이름 등으로만 걸린 경우 — 원래 순서 유지
      return a.minLen - b.minLen;
    }});

    results.innerHTML = '';
    matched.forEach(function(m) {{
      var clone = m.el.cloneNode(true);
      clone.removeAttribute('id');
      m.hitNos.forEach(function(hitKey) {{
        var parts = hitKey.split(':');
        var sub = clone.querySelector('.article-item[data-kind="' + parts[0] + '"][data-no="' + CSS.escape(parts[1]) + '"]');
        if (sub) {{ sub.open = true; sub.classList.add('search-hit'); }}
      }});
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

  // ── AI 의미검색 (임베딩 기반, 완전 클라이언트 사이드 — API 호출 없음) ──
  // 정적 사이트라 서버가 없어서, 법령·고시 조문·별표는 수집 시점(GitHub Actions)에
  // 로컬 임베딩 모델(embed_statutes.py)로 미리 벡터화해 embeddings.json에 저장해두고,
  // 검색 시점엔 브라우저 안에서 정확히 같은 모델(@huggingface/transformers)로 검색어만
  // 그 자리에서 벡터화해 비교한다 — API 요청이 전혀 없어 트래픽이 몰려도 할당량 걱정이
  // 없다(모델을 바꾸면 embed_statutes.py의 MODEL_REPO도 반드시 함께 바꿀 것).
  var aiEnabled = false;
  var aiLoading = false;
  var aiPipeline = null;
  var aiChunks = null; // [{{key, kind, no, vec: Float32Array}}]
  var aiDebounceTimer = null;

  function toggleAiMode() {{
    aiEnabled = !aiEnabled;
    document.getElementById('aiToggleBtn').classList.toggle('active', aiEnabled);
    if (!aiEnabled) {{
      document.getElementById('aiResults').hidden = true;
      return;
    }}
    if (!aiPipeline && !aiLoading) {{
      loadAiModel();
    }} else if (searchQuery) {{
      runAiSearch();
    }}
  }}

  async function loadAiModel() {{
    aiLoading = true;
    var status = document.getElementById('aiStatus');
    status.hidden = false;
    status.textContent = 'AI 모델 로딩 중... (최초 1회, 약 118MB — 다음 방문부터는 브라우저 캐시로 즉시 로딩됩니다)';
    try {{
      var mod = await import('https://cdn.jsdelivr.net/npm/@huggingface/transformers@4.2.0/+esm');
      aiPipeline = await mod.pipeline('feature-extraction', 'Xenova/multilingual-e5-small', {{ dtype: 'q8' }});

      var res = await fetch('embeddings.json');
      var data = await res.json();
      aiChunks = data.chunks.map(function(c) {{
        var bin = atob(c.vec);
        var bytes = new Uint8Array(bin.length);
        for (var i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
        return {{ key: c.key, kind: c.kind, no: c.no, vec: new Float32Array(bytes.buffer) }};
      }});

      status.textContent = 'AI 의미검색 준비 완료 (' + aiChunks.length + '개 조문·별표 인덱싱됨)';
      setTimeout(function() {{ status.hidden = true; }}, 2500);
      aiLoading = false;
      if (searchQuery) runAiSearch();
    }} catch (e) {{
      status.textContent = 'AI 모델 로딩 실패: ' + e.message;
      aiLoading = false;
      console.error(e);
    }}
  }}

  function scheduleAiSearch() {{
    if (!aiEnabled || !aiPipeline) return;
    clearTimeout(aiDebounceTimer);
    aiDebounceTimer = setTimeout(runAiSearch, 400);
  }}

  async function runAiSearch() {{
    var results = document.getElementById('aiResults');
    if (!searchQuery || !aiPipeline || !aiChunks) {{
      results.hidden = true;
      return;
    }}
    var output = await aiPipeline('query: ' + searchQuery, {{ pooling: 'mean', normalize: true }});
    var q = output.data;

    // 법령·고시 하나당 가장 잘 맞는 청크 하나만 남겨 대표점수로 삼음(같은 법령의
    // 여러 조문이 결과 목록을 도배하지 않도록).
    var bestByKey = {{}};
    for (var i = 0; i < aiChunks.length; i++) {{
      var c = aiChunks[i];
      var sim = 0;
      for (var d = 0; d < q.length; d++) sim += q[d] * c.vec[d];
      if (!bestByKey[c.key] || sim > bestByKey[c.key].sim) {{
        bestByKey[c.key] = {{ sim: sim, kind: c.kind, no: c.no }};
      }}
    }}
    var ranked = Object.keys(bestByKey).map(function(key) {{
      var b = bestByKey[key];
      return {{ key: key, sim: b.sim, kind: b.kind, no: b.no }};
    }}).sort(function(a, b) {{ return b.sim - a.sim; }}).slice(0, 5);

    // onclick 문자열 조합 대신 data-* 속성 + addEventListener 사용 — HTML 속성값 안에
    // JS 문자열 리터럴을 따옴표로 또 감싸는 이스케이핑을 피해 실수 여지를 없앤다.
    results.innerHTML = '<div class="ai-results-label">🧠 의미 기반 추천</div>' + ranked.map(function(r) {{
      var nameEl = document.querySelector('#statute-' + CSS.escape(r.key) + ' .statute-name');
      var name = nameEl ? nameEl.textContent : r.key;
      return '<button class="ai-result-item" data-key="' + r.key + '" data-kind="' + r.kind + '" data-no="' + r.no + '">' +
        name + '<span class="ai-result-score">유사도 ' + r.sim.toFixed(2) + '</span></button>';
    }}).join('');
    results.hidden = false;
    results.querySelectorAll('.ai-result-item').forEach(function(btn) {{
      btn.addEventListener('click', function() {{
        jumpToChunk(btn.dataset.key, btn.dataset.kind, btn.dataset.no);
      }});
    }});
  }}

  function jumpToChunk(key, kind, no) {{
    clearAllFilters();
    var card = document.getElementById('statute-' + key);
    if (!card) return;
    card.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
    var detail = card.querySelector('[data-kind="' + kind + '"][data-no="' + CSS.escape(no) + '"]');
    if (detail) {{
      detail.open = true;
      setTimeout(function() {{
        detail.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
        detail.classList.add('deep-link-highlight');
        setTimeout(function() {{ detail.classList.remove('deep-link-highlight'); }}, 2000);
      }}, 300);
    }}
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
