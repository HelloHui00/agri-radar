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


def load_candidates(total_limit=80, per_section_quota=None):
    """Load candidates grouped by section so every section has a floor.

    Returns (candidates, errors, weights).
    Every section gets at least `per_section_quota[section]` candidates if
    the db has them; remaining pool is filled by score across all sections.
    """
    if per_section_quota is None:
        per_section_quota = {
            "journal":              20,   # 科研 - 期刊
            "institution":          12,   # 科研 - 机构
            "industry_satellite":   16,   # 产业界 - 卫星
            "gov":                  16,   # 政府部门
            "industry_agri_company": 16,  # 公司
        }
    db.init_schema()
    conn = db.get_conn()

    # 每板块对应的 tag 集合（先按 tag 进第一个候选池）
    section_tags = {
        "journal":              ["journal"],
        "institution":          ["institution"],
        "industry_satellite":   ["industry_satellite"],
        "gov":                  ["gov"],
        "industry_agri_company":["industry_agri_company"],
    }

    # 行业敏感词黑名单（用作欺炸性过滤,但放宽到不只是印度/SpaceX）
    spam_keywords_strict = [
        "pm modi",        # 纯政治内容
        "election result",
        "stock price soars",
    ]

    # 水印关键词：命中这些词的 google_news 候选降一档优先级（不剔除，只降权）
    low_signal_keywords = [
        "isro", "india space", "indian space", "satsure",
        "spacex", "elon musk", "falcon 9",
        "space startup", "space industry value",
        "nasa administrator",
    ]

    # 按板块独立拉候选
    rows_by_section = {}
    for section, tags in section_tags.items():
        # journal 单独带 limit,其他按 quota
        q = per_section_quota[section]
        # sqlite 不支持数组参数 in,用 LIKE 粗匹配
        like_clauses = " OR ".join([f"source_tags LIKE '%\"{t}\"%'" for t in tags])
        rows = conn.execute(f"""
            SELECT id, title, url, source_name, source_tags, published,
                   summary, score
            FROM items WHERE shown=0 AND ({like_clauses})
            ORDER BY score DESC, published DESC
            LIMIT ?
        """, (q * 2,)).fetchall()  # 取 2 倍方便后面再过滤
        rows_by_section[section] = rows

    # 合并：先按板块各取 quota,再补到 total_limit
    picked_ids = set()
    reps = []
    for section, quota in per_section_quota.items():
        cnt = 0
        for r in rows_by_section[section]:
            if r["id"] in picked_ids:
                continue
            text = (r["title"] + " " + (r["summary"] or "")).lower()
            # 严格黑名单才剔除
            if any(kw in text for kw in spam_keywords_strict):
                continue
            picked_ids.add(r["id"])
            reps.append((section, r))
            cnt += 1
            if cnt >= quota:
                break

    # 剩余位置,按 score 全局排,但每个 section 不得超过其 quota 之上限
    # (防止 fallback 又把 journal 拉到 30+)
    section_max = {s: q + 4 for s, q in per_section_quota.items()}  # 允许 ±4 弹性
    section_cnt = {}
    for _, r in reps:
        # count existing per-section
        pass  # skip, use section from tuple

    # recompute section counts from reps
    section_cnt = {}
    for sec, _ in reps:
        section_cnt[sec] = section_cnt.get(sec, 0) + 1

    if len(reps) < total_limit:
        all_rows = conn.execute("""
            SELECT id, title, url, source_name, source_tags, published,
                   summary, score
            FROM items WHERE shown=0
            ORDER BY score DESC, published DESC
            LIMIT ?
        """, (total_limit * 3,)).fetchall()
        for r in all_rows:
            if len(reps) >= total_limit:
                break
            if r["id"] in picked_ids:
                continue
            tags = json.loads(r["source_tags"] or "[]")
            section = next((s for s, ts in section_tags.items()
                            if any(t in tags for t in ts)), None)
            if not section:
                continue
            # 板块超过 quota+4 就不再塞了
            if section_cnt.get(section, 0) >= section_max.get(section, per_section_quota[section] + 4):
                continue
            text = (r["title"] + " " + (r["summary"] or "")).lower()
            if any(kw in text for kw in spam_keywords_strict):
                continue
            picked_ids.add(r["id"])
            reps.append((section, r))
            section_cnt[section] = section_cnt.get(section, 0) + 1

    # 给低信号条目降权（仅用于给 LLM 参考,不剔除）
    # 实现方式：在传给 LLM 的 dict 里加 'low_signal' 标记
    cands = []
    for section, r in reps:
        text_l = (r["title"] + " " + (r["summary"] or "")).lower()
        low_sig = any(kw in text_l for kw in low_signal_keywords)
        cands.append({
            "id": r["id"],
            "title": r["title"],
            "src": r["source_name"],
            "section": section,
            "tags": r["source_tags"],
            "score": r["score"],
            "pub": r["published"][:16] if r["published"] else "",
            "url": r["url"],
            "summary": (r["summary"] or "")[:220],
            "low_signal": low_sig,
        })

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
    # 分板块加载候选，保证每个板块至少有内容可供 LLM 挑
    cands, errors, weights = load_candidates(
        total_limit=80,
        per_section_quota={
            "journal":              20,
            "institution":          12,
            "industry_satellite":   16,
            "gov":                  16,
            "industry_agri_company": 16,
        },
    )
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
