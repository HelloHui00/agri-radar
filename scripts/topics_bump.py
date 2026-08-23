"""Interactive helper: list topics / sources and adjust weights directly.

Usage:
  python topics_bump.py list
  python topics_bump.py bump topic "农业灾害遥感" +0.5
  python topics_bump.py bump source "谷歌新闻-智慧农业/产业公司" -0.5
  python topics_bump.py watch add "吉林一号 农业"
  python topics_bump.py watch list
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db

def main():
    db.init_schema()
    conn = db.get_conn()
    args = sys.argv[1:]
    if not args or args[0] == "list":
        print("== 话题权重 ==")
        for r in conn.execute("SELECT * FROM topic_prefs ORDER BY multiplier DESC"):
            print(f"  {r['topic']}: {r['multiplier']}")
        print("\n== 来源权重 ==")
        for r in conn.execute("SELECT * FROM source_prefs ORDER BY multiplier DESC"):
            print(f"  {r['source_name']}: {r['multiplier']}")
        print("\n== 关注列表 ==")
        for r in conn.execute("SELECT * FROM watchlist WHERE active=1"):
            print(f"  - {r['pattern']}  ({r['note']})")
        return
    if args[0] == "bump":
        kind, name, delta = args[1], args[2], float(args[3])
        if kind == "topic":
            db.bump_topic(conn, name, delta)
        else:
            db.bump_source(conn, name, delta)
        conn.commit()
        print(f"OK {kind}[{name}] {delta:+}")
    elif args[0] == "watch":
        if args[1] == "add":
            conn.execute(
                "INSERT OR REPLACE INTO watchlist(pattern,active,created_at) VALUES(?,1,?)",
                (args[2], db.now()))
            conn.commit()
            print(f"OK watch + {args[2]}")
        elif args[1] == "list":
            for r in conn.execute("SELECT * FROM watchlist WHERE active=1"):
                print(f"  - {r['pattern']}")

if __name__ == "__main__":
    main()
