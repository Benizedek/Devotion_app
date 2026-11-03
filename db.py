"""Database: structure only. All rules live in Python (see api.py)."""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "devotion.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY,
    username      TEXT NOT NULL UNIQUE COLLATE NOCASE,
    display_name  TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,          -- sha256 of the cookie token; raw token never stored
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TEXT NOT NULL
);

-- "groups" is an SQL keyword, so the table is user_groups
CREATE TABLE IF NOT EXISTS user_groups (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    invite_code TEXT NOT NULL UNIQUE,
    owner_id    INTEGER NOT NULL REFERENCES users(id),
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS group_members (
    group_id  INTEGER NOT NULL REFERENCES user_groups(id) ON DELETE CASCADE,
    user_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    joined_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (group_id, user_id)
);

CREATE TABLE IF NOT EXISTS devotions (
    id         INTEGER PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    entry_date TEXT NOT NULL,             -- YYYY-MM-DD in the writer's local time (travel-friendly)
    title      TEXT NOT NULL DEFAULT '',
    scripture  TEXT NOT NULL DEFAULT '',
    body       TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (user_id, entry_date)
);

-- One row per (devotion, recipient). Recipient is a user OR a group.
CREATE TABLE IF NOT EXISTS devotion_shares (
    id                   INTEGER PRIMARY KEY,
    devotion_id          INTEGER NOT NULL REFERENCES devotions(id) ON DELETE CASCADE,
    shared_with_user_id  INTEGER REFERENCES users(id) ON DELETE CASCADE,
    shared_with_group_id INTEGER REFERENCES user_groups(id) ON DELETE CASCADE,
    created_at           TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS prayers (
    id          INTEGER PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title       TEXT NOT NULL,
    body        TEXT NOT NULL DEFAULT '',
    answered_at TEXT,                     -- NULL = still praying
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- The whole list is shared, so viewers always see the live state.
CREATE TABLE IF NOT EXISTS prayer_list_shares (
    id                   INTEGER PRIMARY KEY,
    owner_id             INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    shared_with_user_id  INTEGER REFERENCES users(id) ON DELETE CASCADE,
    shared_with_group_id INTEGER REFERENCES user_groups(id) ON DELETE CASCADE,
    created_at           TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init():
    DB_PATH.parent.mkdir(exist_ok=True)
    with connect() as conn:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(SCHEMA)
