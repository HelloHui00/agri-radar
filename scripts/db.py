"""SQLite state for agri-radar: items, source weight overrides, watchlist, prefs."""
import sqlite3, os, json, datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.environ.get(
    "AGRI_RADAR_DB",
    os.path.join(BASE_DIR, "data", "agri_radar.db"))

def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_schema():
    with get_conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            url TEXT UNIQUE NOT NULL,
            source_name TEXT,
            source_tags TEXT,        -- JSON array
            published TEXT,
            fetched_at TEXT,
            summary TEXT,
            base_weight REAL,
            score REAL,
            reason TEXT,
            shown INTEGER DEFAULT 0  -- 0 = candidate, 1 = shown, -1 = rejected
        );
        CREATE TABLE IF NOT EXISTS source_prefs (
            source_name TEXT PRIMARY KEY,
            multiplier REAL DEFAULT 1.0,
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS topic_prefs (
            topic TEXT PRIMARY KEY,
            multiplier REAL DEFAULT 1.0,
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS watchlist (
            pattern TEXT PRIMARY KEY,
            active INTEGER DEFAULT 1,
            created_at TEXT,
            note TEXT
        );
        CREATE TABLE IF NOT EXISTS feedback_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT,
            raw_text TEXT,
            action TEXT,
            parsed TEXT
        );
        CREATE TABLE IF NOT EXISTS meta (
            k TEXT PRIMARY KEY,
            v TEXT
        );
        """)

def now():
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def get_source_multiplier(conn, name):
    row = conn.execute("SELECT multiplier FROM source_prefs WHERE source_name=?", (name,)).fetchone()
    return row["multiplier"] if row else 1.0

def get_topic_multiplier(conn, topic):
    row = conn.execute("SELECT multiplier FROM topic_prefs WHERE topic=?", (topic,)).fetchone()
    return row["multiplier"] if row else 1.0

def bump_source(conn, name, delta):
    conn.execute("""
        INSERT INTO source_prefs(source_name, multiplier, updated_at) VALUES(?, ?, ?)
        ON CONFLICT(source_name) DO UPDATE SET multiplier = MAX(0.1, MIN(5.0, multiplier + ?)), updated_at = ?
    """, (name, 1.0 + delta, now(), delta, now()))

def bump_topic(conn, topic, delta):
    conn.execute("""
        INSERT INTO topic_prefs(topic, multiplier, updated_at) VALUES(?, ?, ?)
        ON CONFLICT(topic) DO UPDATE SET multiplier = MAX(0.1, MIN(5.0, multiplier + ?)), updated_at = ?
    """, (topic, 1.0 + delta, now(), delta, now()))


def snapshot_prefs(conn):
    """Return current non-default prefs for display on Pages.

    {
      "topics":   [{"name": ..., "multiplier": float}] (multiplier != 1.0, sorted),
      "sources":  [{"name": ..., "multiplier": float}],
      "watch":    [{"pattern": ..., "note": str}]
    }
    """
    topics = [{"name": r["topic"], "multiplier": r["multiplier"]}
              for r in conn.execute(
                  "SELECT topic, multiplier FROM topic_prefs "
                  "WHERE multiplier != 1.0 ORDER BY ABS(multiplier-1) DESC").fetchall()]
    sources = [{"name": r["source_name"], "multiplier": r["multiplier"]}
               for r in conn.execute(
                   "SELECT source_name, multiplier FROM source_prefs "
                   "WHERE multiplier != 1.0 ORDER BY ABS(multiplier-1) DESC").fetchall()]
    watch = [{"pattern": r["pattern"], "note": r["note"] or ""}
             for r in conn.execute(
                 "SELECT pattern, note FROM watchlist WHERE active=1 "
                 "ORDER BY created_at DESC").fetchall()]
    return {"topics": topics, "sources": sources, "watch": watch}
