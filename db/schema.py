from .connection import get_db

def init_db():
    con = get_db()
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS boxes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            photo TEXT,
            notes TEXT,
            created_at TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            box_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            confidence REAL DEFAULT 0,
            image_url TEXT,
            price_cents INTEGER,
            added_at TEXT,
            FOREIGN KEY (box_id) REFERENCES boxes(id) ON DELETE CASCADE
        )
    """)
    con.commit()
    con.close()

def migrate_db():
    con = get_db()
    for table, cols in {
        "boxes": ["photo", "notes"],
        "items": ["image_url", "price_cents", "added_at"],
    }.items():
        existing = {r["name"] for r in con.execute(f"PRAGMA table_info({table})")}
        for col in cols:
            if col not in existing:
                con.execute(f"ALTER TABLE {table} ADD COLUMN {col} {'TEXT' if col!='price_cents' else 'INTEGER'}")
    con.commit()
    con.close()
