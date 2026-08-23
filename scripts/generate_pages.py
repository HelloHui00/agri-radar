"""Generate GitHub Pages dashboard HTML from latest brief.md.

Generates:
  docs/index.html          - today's brief as the landing page
  docs/archive/YYYY-MM-DD.html  - historical archive (full UI)
  docs/archive/index.html   - beautiful archive index with stats
  docs/stats.json           - cumulative stats for charting
"""
import os, sys, json, html, datetime, re
from collections import defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE, "output")
DOCS_DIR = os.path.join(BASE, "docs")
ARCHIVE_DIR = os.path.join(DOCS_DIR, "archive")
DATA_DIR = os.path.join(BASE, "data")

os.makedirs(ARCHIVE_DIR, exist_ok=True)

CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif;
  background: #f0f2f5; color: #262626; line-height: 1.7; }
.header { background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: white; padding: 2rem 0; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
.header h1 { font-size: 1.8rem; max-width: 900px; margin: 0 auto; padding: 0 1.5rem; }
.header .date { opacity: 0.9; max-width: 900px; margin: 0.3rem auto 0; padding: 0 1.5rem; font-size: 0.95rem; }
.nav { background: white; border-bottom: 1px solid #e5e7eb; padding: 0.8rem 0; }
.nav-inner { max-width: 900px; margin: 0 auto; padding: 0 1.5rem; display: flex; gap: 1.5rem; }
.nav a { color: #059669; text-decoration: none; font-size: 0.9rem; }
.nav a:hover { text-decoration: underline; }
.main { max-width: 900px; margin: 2rem auto; padding: 0 1.5rem; }
.card { background: white; border-radius: 8px; padding: 1.5rem 2rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 1.5rem; }
h2 { color: #059669; font-size: 1.2rem; margin: 1.2rem 0 0.8rem; border-left: 4px solid #10b981; padding-left: 0.6rem; }
hr { border: none; border-top: 1px dashed #d1d5db; margin: 1.5rem 0; }
.num { color: #059669; font-weight: 600; margin-right: 0.3rem; }
.bullet { color: #9ca3af; margin-right: 0.3rem; }
a { color: #2563eb; }
.footer { text-align: center; color: #9ca3af; font-size: 0.85rem; padding: 2rem; }
.badge { display: inline-block; background: #d1fae5; color: #065f46; padding: 0.2rem 0.6rem; border-radius: 12px; font-size: 0.8rem; margin-left: 0.5rem; }
@media (max-width: 640px) {
  .header h1 { font-size: 1.4rem; }
  .card { padding: 1rem 1.2rem; }
}
/* Archive page specific */
.archive-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 1rem; margin-top: 1rem; }
.archive-day { background: white; border: 1px solid #e5e7eb; border-radius: 6px; padding: 1rem; transition: all 0.2s; }
.archive-day:hover { border-color: #10b981; box-shadow: 0 2px 8px rgba(16,185,129,0.15); transform: translateY(-1px); }
.archive-date { font-weight: 600; color: #059669; margin-bottom: 0.3rem; }
.archive-meta { font-size: 0.85rem; color: #6b7280; }
.stats-bar { display: flex; gap: 2rem; padding: 1rem; background: #ecfdf5; border-radius: 6px; margin: 1.2rem 0; }
.stat-item { text-align: center; }
.stat-value { font-size: 1.6rem; font-weight: bold; color: #065f46; }
.stat-label { font-size: 0.85rem; color: #6b7280; margin-top: 0.2rem; }
.month-header { color: #374151; font-size: 1.05rem; font-weight: 600; margin-top: 1.8rem; margin-bottom: 0.8rem;
  padding-bottom: 0.4rem; border-bottom: 2px solid #d1fae5; }
"""

NAV = """
<div class="nav">
  <div class="nav-inner">
    <a href="index.html">📄 今日简报</a>
    <a href="archive/index.html">📚 历史归档</a>
    <a href="https://github.com/hellohui00/agri-radar">⭐ GitHub</a>
  </div>
</div>
"""


def md_to_html(md_text):
    md_text = html.escape(md_text)
    md_text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", md_text)
    md_text = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2" target="_blank">\1</a>', md_text)
    md_text = re.sub(r"^---+$", "<hr>", md_text, flags=re.M)
    md_text = re.sub(r"【(.+?)】", r'<h2>【\1】</h2>', md_text)
    md_text = re.sub(r"^(\d+)\. ", r'<span class="num">\1.</span> ', md_text, flags=re.M)
    md_text = re.sub(r"^- ", r'<span class="bullet">•</span> ', md_text, flags=re.M)
    md_text = md_text.replace("\n\n", "</p><p>").replace("\n", "<br>")
    return f"<div class='content'>{md_text}</div>"


def generate_index(date_str, brief_md, base_path=""):
    """Generate a day page (today or archive)."""
    title_suffix = "今日" if not base_path else date_str
    content_html = md_to_html(brief_md)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🌾 农业遥感情报中心 · {title_suffix}</title>
<style>{CSS}</style>
</head>
<body>
<div class="header">
  <h1>🌾 农业遥感情报中心</h1>
  <div class="date">{date_str} · 每日自动更新</div>
</div>
{NAV}
<div class="main">
  <div class="card" id="today">
{content_html}
  </div>
</div>
<div class="footer">
  <p>由 <a href="https://github.com/hellohui00/agri-radar">agri-radar</a> 自动生成 · 基于 LLM 智能筛选</p>
  <p>数据源：RSE/ISPRS/TGRS/JSTARS · 中科院空天/武大遥感/北师大遥感/马里兰大学 · 吉林一号/Planet/Maxar/Vantor · 农业农村部/USDA/JMA</p>
</div>
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
        <div class="archive-date">📄 {date_str}</div>
        <div class="archive-meta">{items} 条精选</div>
      </div>"""
        months_html += f"""
<div class="month-header">{month_name} <span class="badge">{len(days)}天</span></div>
<div class="archive-grid">{days_html}
</div>"""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>📚 历史简报归档 · 农业遥感情报中心</title>
<style>{CSS}</style>
<style>
body {{ max-width: 1000px; margin: 0 auto; padding: 1.5rem; background: #f0f2f5; }}
.archive-day {{ cursor: pointer; }}
.back-link {{ display: inline-block; margin-bottom: 1rem; color: #059669; }}
</style>
</head>
<body>

<a class="back-link" href="../index.html">← 返回今日简报</a>
<h1 style="color:#059669;margin-bottom:1rem;">📚 历史简报归档</h1>

<div class="stats-bar">
  <div class="stat-item">
    <div class="stat-value">{total_days}</div>
    <div class="stat-label">运行天数</div>
  </div>
  <div class="stat-item">
    <div class="stat-value">{total_items}</div>
    <div class="stat-label">精选条目</div>
  </div>
  <div class="stat-item">
    <div class="stat-value">{avg:.1f}</div>
    <div class="stat-label">日均精选</div>
  </div>
</div>

{months_html}

<div class="footer">
  <p>由 <a href="https://github.com/hellohui00/agri-radar">agri-radar</a> 自动生成 · 基于 LLM 智能筛选</p>
</div>
</body></html>"""


def main():
    if len(sys.argv) > 1:
        date = sys.argv[1]
    else:
        date = datetime.datetime.now().strftime("%Y-%m-%d")

    brief_path = os.path.join(OUTPUT_DIR, f"brief_{date}.md")
    # 扫描所有现有 brief 文件，生成归档
    brief_files = []
    briefs_meta = {}
    if os.path.exists(OUTPUT_DIR):
        for f in sorted(os.listdir(OUTPUT_DIR)):
            if f.startswith("brief_") and f.endswith(".md"):
                date_str = f[6:-3]
                brief_files.append(date_str)
                with open(os.path.join(OUTPUT_DIR, f), encoding="utf-8") as fp:
                    briefs_meta[date_str] = get_brief_metadata(fp.read())["总条数"]

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

    # 生成每个历史日期的 archive/YYYY-MM-DD.html
    archived = 0
    for date_str in brief_files:
        brief_file = os.path.join(OUTPUT_DIR, f"brief_{date_str}.md")
        with open(brief_file, encoding="utf-8") as fp:
            content = fp.read()
        archive_html = generate_index(date_str, content)
        with open(os.path.join(ARCHIVE_DIR, f"{date_str}.html"), "w", encoding="utf-8") as f:
            f.write(archive_html)
        archived += 1
    print(f"✓ archive/: {archived} 天归档页已生成")

    # 生成归档索引页 (聚合展示)
    archive_index_html = generate_archive_index(brief_files, briefs_meta)
    with open(os.path.join(ARCHIVE_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(archive_index_html)
    print(f"✓ docs/archive/index.html ({len(brief_files)} 天)")

    # 写 stats.json
    stats = {
        "last_updated": date,
        "total_days": len(brief_files),
        "total_items": sum(briefs_meta.values()),
        "daily_counts": briefs_meta,
    }
    with open(os.path.join(DOCS_DIR, "stats.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(f"✓ docs/stats.json")


if __name__ == "__main__":
    main()
