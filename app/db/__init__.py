"""Database access: open a connection, and create/upgrade the database on startup."""
import sqlite3
from pathlib import Path

from .. import config
from .migrations import columns, migrate

SCHEMA = (Path(__file__).parent / "schema.sql").read_text()


def connect():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init():
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        cols = columns(conn, "devotions")
        if cols and "observations" not in cols:
            raise SystemExit(
                "data/devotion.db was made by an older version of this app.\n"
                "Delete the data folder and start again (this erases your test accounts).")
        conn.execute("PRAGMA journal_mode = WAL")
        migrate(conn)
        conn.executescript(SCHEMA)
