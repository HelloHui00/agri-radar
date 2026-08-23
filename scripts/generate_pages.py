"""Generate GitHub Pages dashboard HTML from latest brief.md.

Generates:
  docs/index.html          - today's brief as the landing page
  docs/archive/YYYY-MM-DD.html  - historical archive
  docs/stats.json           - JSON for future charting
"""
import os, sys, json, html, datetime, re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE, "output")
DOCS_DIR = os.path.join(BASE, "docs")
ARCHIVE_DIR = os.path.join(DOCS_DIR, "archive")
DATA_DIR = os.path.join(BASE, "data")

os.makedirs(ARCHIVE_DIR, exist_ok=True)


def md_to_html(md_text):
    """Minimal markdown -> HTML (lark_md style)."""
    # escape HTML
    md_text = html.escape(md_text)
    # bold
    md_text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", md_text)
    # links
    md_text = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2" target="_blank">\1</a>', md_text)
    # horizontal rule
    md_text = re.sub(r"^---+$", "<hr>", md_text, flags=re.M)
    # sections
    md_text = re.sub(r"【(.+?)】", r'<h2>【\1】</h2>', md_text)
    # numbered list
    md_text = re.sub(r"^(\d+)\. ", r'<span class="num">\1.</span> ', md_text, flags=re.M)
    # bullet list (watching section)
    md_text = re.sub(r"^- ", r'<span class="bullet">•</span> ', md_text, flags=re.M)
    # line breaks
    md_text = md_text.replace("\n\n", "</p><p>").replace("\n", "<br>")
    return f"<div class='content'>{md_text}</div>"


def generate_index(date_str, brief_md):
    """Generate docs/index.html for today."""
    try:
        with open(os.path.join(BASE, "viewer", "template.html"), encoding="utf-8") as f:
            template = f.read()
    except FileNotFoundError:
        # Fallback inline template
        template = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🌾 农业遥感情报中心 · {date}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif;
  background: #f0f2f5; color: #262626; line-height: 1.7; }}
.header {{ background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: white; padding: 2rem 0; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
.header h1 {{ font-size: 1.8rem; max-width: 900px; margin: 0 auto; padding: 0 1.5rem; }}
.header .date {{ opacity: 0.9; max-width: 900px; margin: 0.3rem auto 0; padding: 0 1.5rem; font-size: 0.95rem; }}
.nav {{ background: white; border-bottom: 1px solid #e5e7eb; padding: 0.8rem 0; }}
.nav-inner {{ max-width: 900px; margin: 0 auto; padding: 0 1.5rem; display: flex; gap: 1.5rem; }}
.nav a {{ color: #059669; text-decoration: none; font-size: 0.9rem; }}
.nav a:hover {{ text-decoration: underline; }}
.main {{ max-width: 900px; margin: 2rem auto; padding: 0 1.5rem; }}
.card {{ background: white; border-radius: 8px; padding: 1.5rem 2rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 1.5rem; }}
h2 {{ color: #059669; font-size: 1.2rem; margin: 1.2rem 0 0.8rem; border-left: 4px solid #10b981; padding-left: 0.6rem; }}
hr {{ border: none; border-top: 1px dashed #d1d5db; margin: 1.5rem 0; }}
.num {{ color: #059669; font-weight: 600; margin-right: 0.3rem; }}
.bullet {{ color: #9ca3af; margin-right: 0.3rem; }}
a {{ color: #2563eb; }}
.footer {{ text-align: center; color: #9ca3af; font-size: 0.85rem; padding: 2rem; }}
.badge {{ display: inline-block; background: #d1fae5; color: #065f46; padding: 0.2rem 0.6rem; border-radius: 12px; font-size: 0.8rem; margin-left: 0.5rem; }}
@media (max-width: 640px) {{
  .header h1 {{ font-size: 1.4rem; }}
  .card {{ padding: 1rem 1.2rem; }}
}}
</style>
</head>
<body>
<div class="header">
  <h1>🌾 农业遥感情报中心</h1>
  <div class="date">{date} · 每日自动更新</div>
</div>
<div class="nav">
  <div class="nav-inner">
    <a href="#today">📄 今日简报</a>
    <a href="#archive">📚 历史归档</a>
    <a href="https://github.com/hellohui00/agri-radar">⭐ GitHub</a>
  </div>
</div>
<div class="main">
  <div class="card" id="today">
{content}
  </div>
</div>
<div class="footer">
  <p>由 <a href="https://github.com/hellohui00/agri-radar">agri-radar</a> 自动生成 · 基于 LLM 智能筛选</p>
  <p>数据源：RSE/ISPRS/TGRS/JSTARS · 中科院空天/武大遥感/北师大遥感/马里兰大学 · 吉林一号/Planet/Maxar/Vantor · 农业农村部/USDA/JMA</p>
</div>
</body>
</html>"""
    content_html = md_to_html(brief_md)
    return template.format(date=date_str, content=content_html)


def generate_archive_link(date_str):
    return f'<li><a href="archive/{date_str}.html">📄 {date_str}</a></li>'


def main():
    if len(sys.argv) > 1:
        date = sys.argv[1]
    else:
        date = datetime.datetime.now().strftime("%Y-%m-%d")

    brief_path = os.path.join(OUTPUT_DIR, f"brief_{date}.md")
    if not os.path.exists(brief_path):
        print(f"简报不存在: {brief_path}")
        sys.exit(0)

    with open(brief_path, encoding="utf-8") as f:
        brief_md = f.read()

    # 生成今日页
    index_html = generate_index(date, brief_md)
    with open(os.path.join(DOCS_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_html)
    print(f"✓ docs/index.html")

    # 历史归档
    archive_html = generate_index(date, brief_md.replace("<div class='content'>",
                                        "<div class='content archive'>"))
    with open(os.path.join(ARCHIVE_DIR, f"{date}.html"), "w", encoding="utf-8") as f:
        f.write(archive_html)
    print(f"✓ docs/archive/{date}.html")

    # 更新归档索引
    archive_files = sorted([f for f in os.listdir(ARCHIVE_DIR) if f.endswith(".html")],
                           reverse=True)
    archive_links = "\n".join([f'<li><a href="archive/{f}">📄 {f[:-5]}</a></li>'
                                for f in archive_files])
    archive_index = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<title>历史归档 - 农业遥感情报中心</title>
<style>
body {{ font-family: sans-serif; max-width: 700px; margin: 2rem auto; padding: 1rem; }}
ul {{ line-height: 2; }}
a {{ color: #059669; }}
</style></head>
<body>
<h1>📚 历史简报归档</h1>
<p><a href="index.html">← 返回今日</a></p>
<ul>
{archive_links}
</ul>
</body></html>"""
    with open(os.path.join(ARCHIVE_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(archive_index)
    print(f"✓ docs/archive/index.html ({len(archive_files)} 天)")

    # Write stats.json for future charting
    stats = {
        "date": date,
        "sources": [],
        "counts": {},
    }
    with open(os.path.join(DOCS_DIR, "stats.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(f"✓ docs/stats.json")


if __name__ == "__main__":
    main()
