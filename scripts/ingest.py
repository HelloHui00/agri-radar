"""Ingest collector JSONL into SQLite, dedupe, and score.

Usage:
    python ingest.py < data/run_xxx.jsonl
    python ingest.py data/run_xxx.jsonl
"""
import sys, os, json, re
from html import unescape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db

TAG_RE = re.compile(r"<[^>]+>")


def clean_summary(s, limit=400):
    if not s:
        return ""
    s = unescape(s)
    s = TAG_RE.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:limit]


def ingest(stream):
    db.init_schema()
    conn = db.get_conn()
    new_cnt = dup_cnt = fail_cnt = 0
    errors = []

    for line in stream:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue

        if not rec.get("ok"):
            errors.append({"source": rec.get("source"),
                           "error": rec.get("error", "unknown")})
            fail_cnt += 1
            continue

        src_name = rec["source"]
        base_w = rec.get("items", [{}])[0].get("base_weight", 3) \
            if rec.get("items") else 3
        mult = db.get_source_multiplier(conn, src_name)

        for it in rec.get("items", []):
            url = it.get("url", "").strip()
            title = it.get("title", "").strip()
            if not url or not title:
                continue
            score = round(it.get("base_weight", base_w) * mult, 3)
            try:
                conn.execute(
                    """INSERT INTO items
                       (title, url, source_name, source_tags, published,
                        fetched_at, summary, base_weight, score)
                       VALUES(?,?,?,?,?,?,?,?,?)""",
                    (title, url, src_name,
                     json.dumps(it.get("tags", []), ensure_ascii=False),
                     it.get("published", ""), db.now(),
                     clean_summary(it.get("summary", "")),
                     it.get("base_weight", base_w), score),
                )
                new_cnt += 1
            except db.sqlite3.IntegrityError:
                dup_cnt += 1

    conn.commit()
    # 失败源清单写进 meta,让 LLM 播报时知道"哪些覆盖缺口"
    conn.execute(
        "INSERT OR REPLACE INTO meta(k,v) VALUES('last_run_errors',?)",
        (json.dumps(errors, ensure_ascii=False),))
    conn.execute(
        "INSERT OR REPLACE INTO meta(k,v) VALUES('last_run_at',?)",
        (db.now(),))
    conn.commit()
    conn.close()

    print(json.dumps({
        "new": new_cnt, "duplicates": dup_cnt,
        "failed_sources": fail_cnt, "errors": errors,
    }, ensure_ascii=False))


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1], encoding="utf-8") as f:
            ingest(f)
    else:
        ingest(sys.stdin)
