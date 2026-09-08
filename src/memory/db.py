"""Memory module — quan ly state qua SQLite.

Owner: Nguoi A
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "state.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
