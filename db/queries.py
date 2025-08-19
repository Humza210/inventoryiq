from datetime import datetime
from typing import List, Tuple, Optional
from .connection import get_db

def list_boxes():
    con = get_db()
    rows = con.execute("SELECT * FROM boxes ORDER BY id DESC").fetchall()
    con.close()
    return rows

def get_box(box_id: int):
    con = get_db()
    row = con.execute("SELECT * FROM boxes WHERE id=?", (box_id,)).fetchone()
    con.close()
    return row

def insert_box(name: str, photo: Optional[str], notes: str = "") -> int:
    con = get_db()
    cur = con.cursor()
    cur.execute(
        "INSERT INTO boxes (name, photo, notes, created_at) VALUES (?,?,?,?)",
        (name, photo, notes, datetime.utcnow().isoformat(timespec="seconds")),
    )
    con.commit()
    box_id = cur.lastrowid
    con.close()
    return box_id

def update_box_name(box_id: int, name: str):
    con = get_db()
    con.execute("UPDATE boxes SET name=? WHERE id=?", (name, box_id))
    con.commit()
    con.close()

def get_items(box_id: int):
    con = get_db()
    rows = con.execute("SELECT * FROM items WHERE box_id=? ORDER BY id ASC", (box_id,)).fetchall()
    con.close()
    return rows

def insert_item(box_id: int, name: str, confidence: float,
                image_url: Optional[str], price_cents: Optional[int]):
    con = get_db()
    con.execute(
        "INSERT INTO items (box_id, name, confidence, image_url, price_cents, added_at) "
        "VALUES (?,?,?,?,?,?)",
        (box_id, name, float(confidence or 0.0), image_url, price_cents,
         datetime.utcnow().isoformat(timespec="seconds")),
    )
    con.commit()
    con.close()

def replace_items(box_id: int, pairs: List[Tuple[str, float, str, Optional[int]]]):
    """pairs = [(name, confidence, image_url, price_cents), ...]"""
    con = get_db()
    cur = con.cursor()
    cur.execute("DELETE FROM items WHERE box_id=?", (box_id,))
    now = datetime.utcnow().isoformat(timespec="seconds")
    cur.executemany(
        "INSERT INTO items (box_id, name, confidence, image_url, price_cents, added_at) "
        "VALUES (?,?,?,?,?,?)",
        [(box_id, n, float(c or 0.0), img, price, now) for (n, c, img, price) in pairs]
    )
    con.commit()
    con.close()

def search_items(q: str):
    """
    Tokenized, case-insensitive search across item AND box names.
    'steel pot' => AND across tokens; each token may match item or box.
    """
    con = get_db()
    terms = [t for t in (q or "").strip().split() if t]
    params = []

    sql = """
        SELECT
          i.name        AS item_name,
          i.confidence  AS confidence,
          i.image_url   AS image_url,
          i.price_cents AS price_cents,
          i.added_at    AS added_at,
          b.id          AS box_id,
          b.name        AS box_name
        FROM items i
        JOIN boxes b ON b.id = i.box_id
    """

    if terms:
        # (i.name LIKE ? OR b.name LIKE ?) AND (i.name LIKE ? OR b.name LIKE ?) ...
        where_clauses = []
        for t in terms:
            like = f"%{t}%"
            where_clauses.append("(i.name LIKE ? COLLATE NOCASE OR b.name LIKE ? COLLATE NOCASE)")
            params.extend([like, like])
        sql += " WHERE " + " AND ".join(where_clauses)
    else:
        # empty query → just show most recent items
        sql += " WHERE 1=1"

    sql += " ORDER BY i.confidence DESC, i.id DESC LIMIT 500"

    rows = con.execute(sql, params).fetchall()
    con.close()
    return rows

def delete_box_and_children(box_id: int) -> Optional[str]:
    """Returns photo filename (if any) to delete from disk."""
    con = get_db()
    cur = con.cursor()
    row = cur.execute("SELECT photo FROM boxes WHERE id=?", (box_id,)).fetchone()
    photo = dict(row).get("photo") if row else None
    cur.execute("PRAGMA foreign_keys = OFF")
    cur.execute("DELETE FROM items WHERE box_id=?", (box_id,))
    cur.execute("DELETE FROM boxes WHERE id=?", (box_id,))
    con.commit()
    cur.execute("PRAGMA foreign_keys = ON")
    con.close()
    return photo
