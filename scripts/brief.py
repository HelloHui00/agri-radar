"""Generate the morning brief: fetch candidates → LLM triage → write
brief.md → mark shown. Provider-agnostic via llm_client.

Usage:
    python scripts/brief.py
"""
import sys, os, json, datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))
import db
import llm_client


def today_str():
    return datetime.datetime.now().strftime("%Y-%m-%d")


def read_file(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def render_prompt(template, mapping):
    for k, v in mapping.items():
        template = template.replace("{{" + k + "}}", str(v))
    return template


def load_candidates(limit=25):
    db.init_schema()
    conn = db.get_conn()
    rows = conn.execute("""
        SELECT id, title, url, source_name, source_tags, published, summary, score
        FROM items WHERE shown=0
        ORDER BY score DESC, published DESC LIMIT ?
    """, (limit * 3,)).fetchall()  # 取 3 倍然后过滤
    
    # 行业敏感词黑名单：标题或 summary 有这些词的不该进 institution/journal
    spam_keywords = [
        "isro", "india space", "indian space", "satsure",  # 印度航天
        "spacex", "elon musk rocket", "falcon 9",          # SpaceX 火箭
        "space startup", "space industry value",            # 航天IT/创投
        "nasa administrator",                               # NASA 行政新闻
    ]
    
    # LLM 前硬过滤：按四板块定义做粗筛，清除噪音
    reps = []
    for r in rows:
        tags = json.loads(r["source_tags"] or "[]")
        # 只保留四板块允许的类别
        if not any(t in ["journal", "institution", "industry_satellite",
                        "gov", "industry_agri_company"] for t in tags):
            continue
        
        # 内容级过滤: 标题或 summary 含 spam 关键词的剔除
        text = (r["title"] + " " + (r["summary"] or "")).lower()
        if any(kw in text for kw in spam_keywords):
            continue
        
        # Google News 来源的，标题含 India/ISRO/Indian 等限定词的疑似噪音
        if "谷歌新闻" in (r["source_name"] or ""):
            if any(kw in text for kw in ["isro", "india space-tech", "satsure",
                                          "pm modi", "india into a global space"]):
                continue
        
        reps.append(r)
        if len(reps) >= limit:
            break
    
    cands = [{"id": r["id"], "title": r["title"], "src": r["source_name"],
              "tags": r["source_tags"],
              "score": r["score"],
              "pub": r["published"][:16] if r["published"] else "",
              "url": r["url"],
              "summary": (r["summary"] or "")[:220]}
             for r in reps]
    er = conn.execute("SELECT v FROM meta WHERE k='last_run_errors'").fetchone()
    errors = json.loads(er["v"]) if er else []
    src_w = {r["source_name"]: r["multiplier"] for r in
             conn.execute("SELECT * FROM source_prefs")}
    top_w = {r["topic"]: r["multiplier"] for r in
             conn.execute("SELECT * FROM topic_prefs")}
    conn.close()
    return cands, errors, {"sources": src_w, "topics": top_w}


def main():
    date = today_str()
    cands, errors, weights = load_candidates(limit=25)
    if not cands:
        print("今天没有新的候选条目。")
        return

    prompt_template = read_file(os.path.join(BASE, "config", "prompts", "brief.md"))
    prompt = render_prompt(prompt_template, {
        "date": date,
        "candidates": json.dumps(cands, ensure_ascii=False, indent=1),
        "errors": json.dumps(errors, ensure_ascii=False) if errors else "无",
        "weights": json.dumps(weights, ensure_ascii=False),
    })

    print(f"发送给 LLM 的候选数: {len(cands)}")
    out = llm_client.chat(prompt, temperature=0.3, max_tokens=4096, timeout=300)

    # 解析 TRIAGE_RESULT
    brief = out
    triage = {}
    if "TRIAGE_RESULT" in out:
        parts = out.split("TRIAGE_RESULT", 1)
        brief = parts[0].strip()
        try:
            triage = json.loads(parts[1].strip().split("\n", 1)[0])
        except Exception:
            pass

    shown_ids = triage.get("shown_ids", [])
    if shown_ids:
        conn = db.get_conn()
        conn.executemany("UPDATE items SET shown=1 WHERE id=?",
                         [(i,) for i in shown_ids])
        conn.commit()
        conn.close()

    out_dir = os.path.join(BASE,
                           llm_client.load_llm_cfg().get("push", {})
                           .get("brief_output_dir", "output"))
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"brief_{date}.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(brief)
    print(f"简报已写入: {out_path}")
    print()
    print(brief)


if __name__ == "__main__":
    main()
