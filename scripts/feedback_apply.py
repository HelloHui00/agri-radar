"""Apply parsed feedback JSON to the database.

Called by the cron LLM after it parses the user's message.
Usage:
    python feedback_apply.py '[{"action":"bump_topic","topic":"农业灾害遥感","delta":0.5}]'
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db

def apply(cmds):
    db.init_schema()
    conn = db.get_conn()
    applied = []
    for c in cmds:
        a = c.get("action")
        if a == "bump_topic":
            db.bump_topic(conn, c["topic"], float(c.get("delta", 0)))
            applied.append(f"topic[{c['topic']}] {'+' if c['delta']>=0 else ''}{c['delta']}")
        elif a == "bump_source":
            db.bump_source(conn, c["source_name"], float(c.get("delta", 0)))
            applied.append(f"source[{c['source_name']}] {'+' if c['delta']>=0 else ''}{c['delta']}")
        elif a == "add_watch":
            conn.execute(
                "INSERT OR REPLACE INTO watchlist(pattern,active,created_at,note) VALUES(?,1,?,?)",
                (c["pattern"], db.now(), c.get("note","")))
            applied.append(f"watch +[{c['pattern']}]")
        elif a == "remove_watch":
            conn.execute("UPDATE watchlist SET active=0 WHERE pattern=?", (c["pattern"],))
            applied.append(f"watch -[{c['pattern']}]")
        elif a == "bump_item":
            # 对某一条的点赞：同时给它的来源和话题加分
            row = conn.execute("SELECT source_name, source_tags FROM items WHERE id=?",
                               (c["item_id"],)).fetchone()
            if row:
                db.bump_source(conn, row["source_name"], 0.3)
                tags = json.loads(row["source_tags"] or "[]")
                for t in tags[:2]:
                    db.bump_topic(conn, t, 0.2)
                applied.append(f"item[{c['item_id']}] approved")
        elif a == "expand":
            applied.append(f"expand requested item[{c['item_id']}] - 由主对话处理")
        else:
            applied.append(f"unknown: {c.get('raw','')}")
    # log
    conn.execute("INSERT INTO feedback_log(ts, raw_text, parsed) VALUES(?,?,?)",
                 (db.now(), json.dumps(cmds, ensure_ascii=False),
                  json.dumps(applied, ensure_ascii=False)))
    conn.commit()
    return applied

if __name__ == "__main__":
    cmds = json.loads(sys.argv[1])
    applied = apply(cmds)
    print("已处理：")
    for a in applied:
        print(" -", a)
