import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "db.sqlite3"

def get_db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con
