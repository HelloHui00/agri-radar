"""Generate GitHub Pages dashboard HTML from latest brief.md.

Generates:
  docs/index.html          - today's brief as the landing page
  docs/archive/YYYY-MM-DD.html  - historical archive (full UI)
  docs/archive/index.html   - beautiful archive index with stats
  docs/stats.json           - cumulative stats for charting
"""
import os, sys, json, html, datetime, re, urllib.parse
from collections import defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE, "output")
DOCS_DIR = os.path.join(BASE, "docs")
ARCHIVE_DIR = os.path.join(DOCS_DIR, "archive")
DATA_DIR = os.path.join(BASE, "data")

# 添加 scripts 路径,引用 db 快照
sys.path.insert(0, os.path.join(BASE, "scripts"))
try:
    import db as _db
except ImportError:
    _db = None

os.makedirs(ARCHIVE_DIR, exist_ok=True)

CSS = """
/* ============ Design tokens ============ */
:root {
  --bg:               #fafbf9;
  --bg-elev:          #ffffff;
  --bg-tint:          #f0fdf4;
  --bg-tint-2:        #ecfdf5;
  --border:           #e2e8f0;
  --border-strong:    #cbd5e1;
  --text:             #0f172a;
  --text-2:           #334155;
  --text-3:           #64748b;
  --text-4:           #94a3b8;
  --accent:           #059669;
  --accent-strong:    #047857;
  --accent-soft:      #d1fae5;
  --accent-faint:     #ecfdf5;
  --link:             #059669;
  --link-hover:       #047857;
  --shadow-color:     5 150 105;
  --radius-card:      10px;
  --radius-chip:      999px;
  --radius-block:     6px;
  --font-display:     "Söhne Breit", "Cabinet Grotesk", "Inter Display",
                      -apple-system, BlinkMacSystemFont, "PingFang SC",
                      "Microsoft YaHei", sans-serif;
  --font-mono:        ui-monospace, "SF Mono", "JetBrains Mono",
                      Menlo, Consolas, monospace;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg:               #0b0f0c;
    --bg-elev:          #101613;
    --bg-tint:          #0e241a;
    --bg-tint-2:        #12291e;
    --border:           #1f2a24;
    --border-strong:    #2d3a33;
    --text:             #e6f0ea;
    --text-2:           #b7c9c0;
    --text-3:           #7d8f87;
    --text-4:           #4e5f57;
    --accent:           #34d399;
    --accent-strong:    #6ee7b7;
    --accent-soft:      #064e3b;
    --accent-faint:     #022c22;
    --link:             #34d399;
    --link-hover:       #6ee7b7;
    --shadow-color:     0 0 0;
  }
}

/* ============ Reset ============ */
* { margin: 0; padding: 0; box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  font-family: var(--font-display);
  background: var(--bg);
  color: var(--text);
  line-height: 1.7;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  font-feature-settings: "tnum" 1, "cv11" 1;
  min-height: 100dvh;
}
::selection { background: var(--accent-soft); color: var(--accent-strong); }

/* ============ Header (Hero: eyebrow + title + date, max 3) ============ */
.site-head {
  background: var(--bg-elev);
  border-bottom: 1px solid var(--border);
  padding: 1.4rem 0 1.15rem;
}
.site-head-inner {
  max-width: 880px; margin: 0 auto; padding: 0 1.5rem;
  display: flex; align-items: baseline; justify-content: space-between;
  gap: 1rem; flex-wrap: wrap;
}
.eyebrow {
  font-family: var(--font-mono);
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--accent);
  margin-bottom: 0.35rem;
}
.site-head h1 {
  font-size: 1.45rem;
  font-weight: 650;
  letter-spacing: -0.02em;
  color: var(--text);
  line-height: 1.25;
}
.site-head .date {
  font-family: var(--font-mono);
  font-size: 0.78rem;
  color: var(--text-3);
  letter-spacing: 0.01em;
  padding-top: 0.4rem;
}

/* ============ Nav (single line, height cap 48px) ============ */
.nav {
  background: var(--bg-elev);
  border-bottom: 1px solid var(--border);
  padding: 0.55rem 0;
}
.nav-inner {
  max-width: 880px; margin: 0 auto; padding: 0 1.5rem;
  display: flex; gap: 1.4rem; align-items: center;
  overflow-x: auto; scrollbar-width: none;
}
.nav-inner::-webkit-scrollbar { display: none; }
.nav a {
  color: var(--text-3);
  text-decoration: none;
  font-size: 0.82rem;
  font-weight: 500;
  white-space: nowrap;
  border-bottom: 1px solid transparent;
  padding-bottom: 0.15rem;
  transition: color 0.15s ease, border-color 0.15s ease;
}
.nav a:hover { color: var(--accent); border-bottom-color: var(--accent); }
.nav a.primary { color: var(--accent); font-weight: 600; }

/* ============ Main ============ */
.main { max-width: 880px; margin: 2rem auto 3rem; padding: 0 1.5rem; }

/* Stats bar (subtle, tinted shadow) */
.stats-bar {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 1px;
  background: var(--border);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  overflow: hidden;
  margin-bottom: 1.8rem;
}
.stat-item {
  background: var(--bg-elev);
  padding: 1rem 1.1rem 0.9rem;
  text-align: left;
}
.stat-label {
  font-family: var(--font-mono);
  font-size: 0.7rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--text-4);
  margin-bottom: 0.35rem;
}
.stat-value {
  font-size: 1.6rem;
  font-weight: 630;
  color: var(--accent);
  line-height: 1.05;
  font-variant-numeric: tabular-nums;
}

/* ============ Content card ============ */
.card {
  background: var(--bg-elev);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  padding: 2rem 2.2rem;
  box-shadow: 0 1px 2px rgba(var(--shadow-color) / 0.04),
              0 2px 8px rgba(var(--shadow-color) / 0.05);
}
@media (max-width: 640px) { .card { padding: 1.3rem 1.1rem; border-radius: 8px; } }

/* Section headers 【科研】 etc. - "chip" treatment, tinted accent */
h2 {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.95rem;
  font-weight: 650;
  letter-spacing: -0.005em;
  color: var(--accent-strong);
  background: var(--accent-faint);
  border: 1px solid var(--accent-soft);
  padding: 0.3rem 0.85rem 0.32rem;
  border-radius: var(--radius-chip);
  margin: 1.6rem 0 0.9rem;
}
h2::before {
  content: "";
  width: 6px; height: 6px;
  border-radius: 50%;
  background: var(--accent);
  flex-shrink: 0;
}
h2:first-of-type { margin-top: 0.4rem; }

/* List items */
.num, .bullet { color: var(--accent); font-weight: 600; margin-right: 0.4rem; }
.num { font-variant-numeric: tabular-nums; }

/* Body text */
.card p { color: var(--text-2); margin-bottom: 0.85rem; max-width: 65ch; }
.card strong { color: var(--text); font-weight: 620; }

/* Links */
.card a {
  color: var(--link);
  text-decoration: none;
  border-bottom: 1px solid transparent;
  transition: color 0.15s ease, border-color 0.15s ease;
}
.card a:hover { color: var(--link-hover); border-bottom-color: var(--accent-soft); }

/* Divider */
hr {
  border: none;
  border-top: 1px solid var(--border);
  margin: 1.8rem 0;
}

/* Badge (use sparingly) */
.badge {
  display: inline-block;
  font-family: var(--font-mono);
  font-size: 0.68rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  background: var(--accent-faint);
  color: var(--accent-strong);
  border: 1px solid var(--accent-soft);
  padding: 0.15rem 0.55rem 0.17rem;
  border-radius: var(--radius-chip);
  white-space: nowrap;
}

/* ============ Footer ============ */
.footer {
  text-align: center;
  color: var(--text-4);
  font-size: 0.78rem;
  padding: 2.5rem 1.5rem 3rem;
  border-top: 1px solid var(--border);
  margin-top: 3rem;
}
.footer p + p { margin-top: 0.3rem; }
.footer a { color: var(--text-3); text-decoration: none; border-bottom: 1px solid var(--border-strong); }
.footer a:hover { color: var(--accent); border-bottom-color: var(--accent); }
.footer .byline { font-weight: 500; color: var(--text-3); }
.footer .sources-line { color: var(--text-4); letter-spacing: 0.002em; line-height: 1.55; }

/* ============ Archive specific ============ */
.archive-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 0.9rem;
  margin-top: 0.9rem;
}
.archive-day {
  background: var(--bg-elev);
  border: 1px solid var(--border);
  border-radius: var(--radius-block);
  padding: 0.95rem 1rem 0.85rem;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
  cursor: pointer;
}
.archive-day:hover {
  border-color: var(--accent);
  box-shadow: 0 2px 12px rgba(var(--shadow-color) / 0.1);
}
.archive-date {
  font-weight: 630;
  color: var(--accent-strong);
  font-size: 0.92rem;
  letter-spacing: -0.005em;
  margin-bottom: 0.25rem;
}
.archive-meta { font-size: 0.78rem; color: var(--text-3); font-variant-numeric: tabular-nums; }

.month-header {
  font-family: var(--font-mono);
  font-size: 0.74rem;
  font-weight: 600;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--text-3);
  margin-top: 2rem;
  margin-bottom: 0.6rem;
  padding-bottom: 0.4rem;
  border-bottom: 1px solid var(--border);
  display: flex; align-items: baseline; justify-content: space-between; gap: 0.5rem;
}
.month-header .badge { transform: translateY(-1px); }

/* ============ Feedback card ============ */
.feedback-card {
  background: var(--bg-elev);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  padding: 1.4rem 1.5rem 1.3rem;
  margin-top: 1.8rem;
  box-shadow: 0 1px 2px rgba(var(--shadow-color) / 0.04);
}
.fb-eyebrow {
  font-family: var(--font-mono);
  font-size: 0.68rem;
  font-weight: 600;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--accent);
  margin-bottom: 0.3rem;
}
.fb-title {
  font-size: 1.05rem;
  font-weight: 650;
  letter-spacing: -0.01em;
  color: var(--text);
  margin-bottom: 0.4rem;
}
.fb-desc {
  font-size: 0.85rem;
  color: var(--text-3);
  margin-bottom: 1rem;
  line-height: 1.6;
}
.fb-quick-row {
  display: flex; flex-wrap: wrap; gap: 0.45rem;
  margin-bottom: 0.9rem;
}
.fb-chip {
  padding: 0.28rem 0.75rem;
  border-radius: var(--radius-chip);
  border: 1px solid var(--accent-soft);
  background: var(--accent-faint);
  color: var(--accent-strong);
  font-size: 0.78rem;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease;
  white-space: nowrap;
}
.fb-chip:hover { background: var(--accent-soft); border-color: var(--accent); }
.fb-chip:active { transform: translateY(1px); }
.fb-textarea {
  width: 100%;
  min-height: 96px;
  font-family: var(--font-display);
  font-size: 0.9rem;
  color: var(--text);
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-block);
  padding: 0.65rem 0.85rem;
  resize: vertical;
  line-height: 1.6;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
.fb-textarea:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-faint);
}
.fb-actions {
  display: flex; gap: 0.6rem; align-items: center;
  margin-top: 0.85rem;
  flex-wrap: wrap;
}
.fb-btn {
  display: inline-flex; align-items: center; gap: 0.4rem;
  padding: 0.5rem 1.05rem;
  border-radius: var(--radius-block);
  border: 1px solid var(--accent);
  background: var(--accent);
  color: #ffffff;
  font-size: 0.82rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s ease, transform 0.1s ease;
  text-decoration: none;
}
.fb-btn:hover { background: var(--accent-strong); border-color: var(--accent-strong); }
.fb-btn:active { transform: translateY(1px); }
.fb-btn.secondary {
  background: transparent;
  color: var(--accent);
  border-color: var(--border-strong);
}
.fb-btn.secondary:hover {
  background: var(--accent-faint);
  border-color: var(--accent);
  color: var(--accent-strong);
}
.fb-note {
  font-size: 0.72rem;
  color: var(--text-4);
  margin-top: 0.7rem;
  font-family: var(--font-mono);
}
.fb-status {
  font-size: 0.8rem;
  color: var(--accent-strong);
  margin-left: 0.4rem;
}

/* ============ Current prefs snapshot ============ */
.prefs-card {
  background: var(--bg-elev);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  padding: 1rem 1.3rem;
  margin-bottom: 1.5rem;
  font-size: 0.85rem;
}
.prefs-title {
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--text-4);
  font-family: var(--font-mono);
  margin-bottom: 0.55rem;
}
.prefs-row {
  display: flex; flex-wrap: wrap; gap: 0.4rem;
  align-items: center;
}
.prefs-row + .prefs-row { margin-top: 0.4rem; }
.prefs-tag {
  display: inline-block;
  padding: 0.15rem 0.6rem;
  border-radius: var(--radius-chip);
  font-size: 0.74rem;
  font-weight: 500;
  border: 1px solid var(--border-strong);
  color: var(--text-3);
  background: var(--bg);
  font-variant-numeric: tabular-nums;
}
.prefs-tag.like {
  border-color: var(--accent-soft);
  color: var(--accent-strong);
  background: var(--accent-faint);
}
.prefs-tag.dislike {
  border-color: #fecaca;
  color: #b91c1c;
  background: #fef2f2;
}
.prefs-tag.watch {
  border-color: #fde68a;
  color: #92400e;
  background: #fffbeb;
}
@media (prefers-color-scheme: dark) {
  .prefs-tag.dislike { border-color: #7f1d1d; color: #fca5a5; background: #450a0a; }
  .prefs-tag.watch   { border-color: #78350f; color: #fbbf24; background: #451a03; }
}

/* ============ Reduced motion ============ */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { transition-duration: 0.01ms !important; animation-duration: 0.01ms !important; }
}
"""

NAV = """
<div class="nav">
  <div class="nav-inner">
    <a href="index.html" class="primary">今日简报</a>
    <a href="archive/index.html">历史归档</a>
    <a href="https://github.com/hellohui00/agri-radar">GitHub</a>
  </div>
</div>
"""


def md_to_html(md_text):
    md_text = html.escape(md_text)
    md_text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", md_text)
    md_text = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2" target="_blank" rel="noopener">\1</a>', md_text)
    md_text = re.sub(r"^---+$", "<hr>", md_text, flags=re.M)
    # 页首一级标题：整场日报题，已由页面 hero 呈现，卡片内不再重复
    md_text = re.sub(r"^#\s+.+$", "", md_text, flags=re.M)
    # 章节头【章节】（字符串可能被 markdown 二级标题包住）
    md_text = re.sub(r"^#{1,6}\s*【(.+?)】\s*$", r"\n\n【\1】\n\n", md_text, flags=re.M)
    md_text = re.sub(r"^【(.+?)】\s*$", r"\n\n【\1】\n\n", md_text, flags=re.M)
    # numbered and bullet list markers (start of line)
    md_text = re.sub(r"^(\d+)\.\s+", r'<span class="num">\1.</span> ', md_text, flags=re.M)
    md_text = re.sub(r"^-\s+", r'<span class="bullet">•</span> ', md_text, flags=re.M)
    # 按空行拆段；每段单独决定包 <p> 还是直接放块级元素
    out_blocks = []
    for blk in re.split(r"\n\s*\n", md_text):
        blk = blk.strip()
        if not blk:
            continue
        if blk.startswith("【") and blk.endswith("】"):
            sec = blk[1:-1]
            out_blocks.append(f"<h2>【{sec}】</h2>")
        elif blk == "<hr>":
            out_blocks.append("<hr>")
        else:
            out_blocks.append(f"<p>{blk.replace(chr(10), '<br>')}</p>")
    return f"<div class='content'>{''.join(out_blocks)}</div>"


def generate_index(date_str, brief_md, base_path=""):
    """Generate a day page (today or archive)."""
    title_suffix = "今日" if not base_path else date_str
    content_html = md_to_html(brief_md)
    meta = get_brief_metadata(brief_md)
    stats_html = ""
    if meta["总条数"] > 0:
        stats_html = f"""
<div class="stats-bar" role="region" aria-label="今日统计">
  <div class="stat-item">
    <div class="stat-label">今日精选</div>
    <div class="stat-value">{meta["总条数"]}</div>
  </div>
  <div class="stat-item">
    <div class="stat-label">科研</div>
    <div class="stat-value">{meta["科研"]}</div>
  </div>
  <div class="stat-item">
    <div class="stat-label">产业界</div>
    <div class="stat-value">{meta["产业界"]}</div>
  </div>
  <div class="stat-item">
    <div class="stat-label">政府部门</div>
    <div class="stat-value">{meta["政府部门"]}</div>
  </div>
  <div class="stat-item">
    <div class="stat-label">公司</div>
    <div class="stat-value">{meta["公司"]}</div>
  </div>
</div>"""

    # 偏好快照 + 反馈表单 (仅在今日主页显示,归档页省略以减重)
    prefs_html = _prefs_snapshot_html() if not base_path else ""
    feedback_html = _feedback_card_html(date_str) if not base_path else ""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>农业遥感情报中心 · {title_suffix}</title>
<style>{CSS}</style>
</head>
<body>

<header class="site-head">
  <div class="site-head-inner">
    <div>
      <div class="eyebrow">Agri-Remote-Sensing Intelligence</div>
      <h1>农业遥感情报中心</h1>
    </div>
    <div class="date">{date_str}</div>
  </div>
</header>

{NAV}

<main class="main">
{stats_html}
{prefs_html}
  <article class="card" id="today">
{content_html}
  </article>
{feedback_html}
</main>

<footer class="footer">
  <p class="byline">由 <a href="https://github.com/hellohui00/agri-radar">agri-radar</a> 自动生成</p>
  <p class="sources-line">RSE · ISPRS J P&R · IEEE TGRS · JAG · CEA · ESSD · Nature · Science · PNAS · ESA · NASA · 农业农村部 · 吉林一号 · Planet · Maxar</p>
</footer>

</body>
</html>"""


def get_brief_metadata(brief_md):
    """Extract useful metadata from a brief markdown."""
    section_counts = {}
    current = None
    for line in brief_md.splitlines():
        m = re.match(r"【(.+?)】", line)
        if m:
            current = m.group(1)
            section_counts[current] = 0
        elif current and re.match(r"^\d+\.", line.strip()):
            section_counts[current] += 1
    # 简洁统计
    counts = {"科研": section_counts.get("科研", 0),
              "产业界": section_counts.get("产业界", 0),
              "政府部门": section_counts.get("政府部门", 0),
              "公司": section_counts.get("公司", 0),
              "跟踪": section_counts.get("跟踪", 0)}
    counts["总条数"] = sum([v for k, v in counts.items() if k != "跟踪"])
    return counts


REPO_OWNER = os.environ.get("AGRI_RADAR_REPO", "HelloHui00/agri-radar")


def _prefs_snapshot_html():
    """Render a small 'current preferences' card. Empty if db missing or no prefs set."""
    if _db is None:
        return ""
    try:
        _db.init_schema()
        conn = _db.get_conn()
        snap = _db.snapshot_prefs(conn)
        conn.close()
    except Exception:
        return ""

    rows = []
    if snap["topics"]:
        chips = []
        for t in snap["topics"][:6]:
            cls = "like" if t["multiplier"] > 1.0 else "dislike"
            sign = "+" if t["multiplier"] > 1.0 else ""
            delta = t["multiplier"] - 1.0
            chips.append(f'<span class="prefs-tag {cls}">{html.escape(t["name"])} {sign}{delta:+.1f}</span>')
        rows.append(f'<div class="prefs-row"><strong>话题偏好</strong>&nbsp;{"".join(chips)}</div>')

    if snap["sources"]:
        chips = []
        for s in snap["sources"][:6]:
            cls = "like" if s["multiplier"] > 1.0 else "dislike"
            sign = "+" if s["multiplier"] > 1.0 else ""
            delta = s["multiplier"] - 1.0
            chips.append(f'<span class="prefs-tag {cls}">{html.escape(s["name"])} {sign}{delta:+.1f}</span>')
        rows.append(f'<div class="prefs-row"><strong>来源偏好</strong>&nbsp;{"".join(chips)}</div>')

    if snap["watch"]:
        chips = [f'<span class="prefs-tag watch">👁 {html.escape(w["pattern"])}</span>'
                 for w in snap["watch"][:5]]
        rows.append(f'<div class="prefs-row"><strong>正在跟踪</strong>&nbsp;{"".join(chips)}</div>')

    if not rows:
        return ""

    return f"""
<div class="prefs-card" role="complementary" aria-label="当前偏好">
  <div class="prefs-title">📌 当前你的偏好</div>
{''.join(rows)}
</div>"""


def _feedback_card_html(date_str):
    """Render the feedback form. Quick chips inject text; textarea goes to GitHub
    Issues via query-param prefill URL (A1 plan); '复制'降级到剪贴板.
    """
    quick_chips = [
        ("多推 PhiSat-2", "多推 PhiSat-2 星上处理 农业"),
        ("多推 高光谱", "多推 高光谱遥感进展"),
        ("多推 干旱监测", "多推 干旱监测与墒情"),
        ("少推 渔业", "少推 渔业"),
        ("少推 政策法规解读", "少推 政府政策解读"),
        ("跟踪 CropWatch", "跟踪 CropWatch 新数据发布"),
        ("跟踪 吉林一号", "跟踪 吉林一号 农业"),
    ]
    chips_html = "".join(
        '<button type="button" class="fb-chip" data-inject="{}">{}</button>'.format(
            html.escape(v, quote=True), html.escape(k))
        for k, v in quick_chips)

    page_url = "https://" + REPO_OWNER.replace("/", ".github.io/") + "/"

    html_tmpl = """
<div class="feedback-card" role="form" aria-label="反馈表">
  <div class="fb-eyebrow">Feedback</div>
  <div class="fb-title">告诉我们你想看什么、不想看什么</div>
  <div class="fb-desc">
    点击下面的快捷指令快速填充,也可以直接写。明早 5 点的 workflow 会读取你的反馈,并据此调整推送。
  </div>
  <div class="fb-quick-row">__CHIPS__</div>
  <textarea
    id="fb-text"
    class="fb-textarea"
    placeholder="例如:多推 高光谱 / 少推 渔业 / 跟踪 Maxar 农业"
    aria-label="反馈内容"
    maxlength="2000"></textarea>
  <div class="fb-actions">
    <button type="button" id="fb-submit" class="fb-btn">提交到 GitHub</button>
    <button type="button" id="fb-copy" class="fb-btn secondary">复制到剪贴板</button>
    <span class="fb-status" id="fb-status" role="status" aria-live="polite"></span>
  </div>
  <div class="fb-note">
    提交后会打开 GitHub 新建 Issue 页(带上你写的内容),需要你点一下"Submit"完成创建。
    如果你没有 GitHub 账号,可以点"复制到剪贴板",把内容发到我们飞书群/邮箱。
  </div>
</div>

<script>
(function() {
  var repo = __REPO__;
  var dateStr = __DATE__;
  var pageUrl = __PAGE_URL__;
  var issueTitle = "[Feedback] " + dateStr + " user";
  var textEl = document.getElementById("fb-text");
  var statusEl = document.getElementById("fb-status");

  // Quick chip -> append to textarea
  document.querySelectorAll(".fb-chip").forEach(function(btn) {
    btn.addEventListener("click", function() {
      var inject = btn.getAttribute("data-inject") || "";
      if (textEl.value.trim()) {
        textEl.value = textEl.value.trim() + "\n" + inject;
      } else {
        textEl.value = inject;
      }
      textEl.focus();
    });
  });

  // Submit -> jump to GitHub Issues/new with prefilled title+body+labels
  document.getElementById("fb-submit").addEventListener("click", function() {
    var body = textEl.value.trim();
    if (!body) {
      statusEl.textContent = "请先写一点内容";
      textEl.focus();
      return;
    }
    var fullBody = "**来源页面**: " + pageUrl + "\n" +
                  "**提交日期**: " + dateStr + "\n\n" +
                  "**反馈内容**:\n" + body;
    var url = "https://github.com/" + repo + "/issues/new" +
              "?title=" + encodeURIComponent(issueTitle) +
              "&body=" + encodeURIComponent(fullBody) +
              "&labels=feedback";
    window.open(url, "_blank", "noopener");
    statusEl.textContent = "已打开 GitHub Issue 预填页 →";
  });

  // Copy -> clipboard
  document.getElementById("fb-copy").addEventListener("click", function() {
    var body = textEl.value.trim();
    if (!body) {
      statusEl.textContent = "请先写一点内容";
      textEl.focus();
      return;
    }
    var fullBody = "[" + dateStr + " feedback]\n" + body;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(fullBody).then(function() {
        statusEl.textContent = "已复制";
      }).catch(function() {
        fallbackCopy();
      });
    } else {
      fallbackCopy();
    }
    function fallbackCopy() {
      textEl.select();
      document.execCommand("copy");
      statusEl.textContent = "已复制";
    }
  });
})();
</script>
"""
    return (html_tmpl
            .replace("__CHIPS__", chips_html)
            .replace("__REPO__", json.dumps(REPO_OWNER))
            .replace("__DATE__", json.dumps(date_str))
            .replace("__PAGE_URL__", json.dumps(page_url)))


def generate_archive_index(archive_files, briefs_meta):
    """Generate a rich archive index page with stats and grouped-by-month list."""
    total_days = len(archive_files)
    total_items = sum(briefs_meta.values())
    avg = total_items / total_days if total_days else 0

    # 按月份分组
    by_month = defaultdict(list)
    for date_str in sorted(archive_files, reverse=True):
        if date_str == "index.html":
            continue
        month = date_str[:7]  # YYYY-MM
        items = briefs_meta.get(date_str, 0)
        by_month[month].append((date_str, items))

    # 分页 HTML
    months_html = ""
    for month in sorted(by_month.keys(), reverse=True):
        year, mon = month.split("-")
        month_name = f"{year}年{int(mon)}月"
        days = by_month[month]
        days_html = ""
        for date_str, items in days:
            days_html += f"""
      <div class="archive-day" onclick="window.location.href='{date_str}.html'">
        <div class="archive-date">{date_str}</div>
        <div class="archive-meta">{items} 条精选</div>
      </div>"""
        months_html += f"""
<div class="month-header"><span>{month_name}</span> <span class="badge">{len(days)} 天</span></div>
<div class="archive-grid">{days_html}
</div>"""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>历史简报归档 · 农业遥感情报中心</title>
<style>{CSS}</style>
<style>
body {{ background: var(--bg); }}
.arch-wrap {{ max-width: 880px; margin: 0 auto; padding: 2.2rem 1.5rem 3rem; }}
.back-link {{
  display: inline-block;
  margin-bottom: 1.2rem;
  color: var(--accent);
  text-decoration: none;
  font-size: 0.85rem;
  font-weight: 500;
}}
.back-link:hover {{ color: var(--accent-strong); }}
.arch-title {{
  font-size: 1.5rem;
  font-weight: 650;
  letter-spacing: -0.02em;
  color: var(--text);
  margin-bottom: 1.6rem;
}}
</style>
</head>
<body>

<div class="arch-wrap">

<a class="back-link" href="../index.html">← 返回今日简报</a>

<h1 class="arch-title">历史简报归档</h1>

<div class="stats-bar" role="region" aria-label="归档统计">
  <div class="stat-item">
    <div class="stat-label">运行天数</div>
    <div class="stat-value">{total_days}</div>
  </div>
  <div class="stat-item">
    <div class="stat-label">精选条目</div>
    <div class="stat-value">{total_items}</div>
  </div>
  <div class="stat-item">
    <div class="stat-label">日均精选</div>
    <div class="stat-value">{avg:.1f}</div>
  </div>
</div>

{months_html}

<footer class="footer">
  <p class="byline">由 <a href="https://github.com/hellohui00/agri-radar">agri-radar</a> 自动生成</p>
</footer>

</div>

</body>
</html>"""


def main():
    if len(sys.argv) > 1:
        date = sys.argv[1]
    else:
        date = datetime.datetime.now().strftime("%Y-%m-%d")

    brief_path = os.path.join(OUTPUT_DIR, f"brief_{date}.md")
    # 扫描: 源 brief 和平盘 html 两侧都算归档索引依据
    # 解决"归档索引遗漏跨日 html"的 bug:
    # 之前仅看 output/brief_*.md, 若 workflow 某天没产出 brief, 对应日期
    # 即便已经存到 docs/archive/<date>.html 也不会出现在索引里。
    all_dates = []   # 归档索引用
    briefs_meta = {}
    render_dates = []  # 需要重新生成 html 的(只在有源 brief 时)

    if os.path.exists(OUTPUT_DIR):
        for f in sorted(os.listdir(OUTPUT_DIR)):
            if f.startswith("brief_") and f.endswith(".md"):
                date_str = f[6:-3]
                all_dates.append(date_str)
                render_dates.append(date_str)
                with open(os.path.join(OUTPUT_DIR, f), encoding="utf-8") as fp:
                    briefs_meta[date_str] = get_brief_metadata(fp.read())["总条数"]

    # 同时收集已存在的 docs/archive/YYYY-MM-DD.html
    # 若没对应源 brief,则只 list 归档索引,不重新生成 html
    if os.path.exists(ARCHIVE_DIR):
        for f in sorted(os.listdir(ARCHIVE_DIR)):
            if re.match(r"^\d{4}-\d{2}-\d{2}\.html$", f):
                date_str = f[:-5]
                if date_str not in all_dates:
                    all_dates.append(date_str)
                    # 从 html 中数条目数(class="num">) 作归档估算
                    html_path = os.path.join(ARCHIVE_DIR, f)
                    try:
                        with open(html_path, encoding="utf-8") as fp:
                            content = fp.read()
                        briefs_meta[date_str] = len(re.findall(r'class="num">', content))
                    except Exception:
                        briefs_meta[date_str] = 0

    # 生成今日 index.html (如果能读到最新简报)
    if os.path.exists(brief_path):
        with open(brief_path, encoding="utf-8") as f:
            brief_md = f.read()
        index_html = generate_index(date, brief_md)
        with open(os.path.join(DOCS_DIR, "index.html"), "w", encoding="utf-8") as f:
            f.write(index_html)
        print(f"✓ docs/index.html")
    else:
        print(f"⚠ 简报不存在: {brief_path}, 跳过今日页")

    # 仅为有源 brief 的日期重新生成 archive/YYYY-MM-DD.html
    archived = 0
    for date_str in render_dates:
        brief_file = os.path.join(OUTPUT_DIR, f"brief_{date_str}.md")
        with open(brief_file, encoding="utf-8") as fp:
            content = fp.read()
        archive_html = generate_index(date_str, content)
        with open(os.path.join(ARCHIVE_DIR, f"{date_str}.html"), "w", encoding="utf-8") as f:
            f.write(archive_html)
        archived += 1
    print(f"✓ archive/: {archived} 天归档页已生成 (索引共 {len(all_dates)} 天)")

    # 生成归档索引页 (聚合展示)
    archive_index_html = generate_archive_index(all_dates, briefs_meta)
    with open(os.path.join(ARCHIVE_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(archive_index_html)
    print(f"✓ docs/archive/index.html ({len(all_dates)} 天)")

    # 写 stats.json
    stats = {
        "last_updated": date,
        "total_days": len(all_dates),
        "total_items": sum(briefs_meta.values()),
        "daily_counts": briefs_meta,
    }
    with open(os.path.join(DOCS_DIR, "stats.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(f"✓ docs/stats.json")


if __name__ == "__main__":
    main()
