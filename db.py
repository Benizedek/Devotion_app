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
    theme         TEXT NOT NULL DEFAULT 'warm',   -- color theme name (see app.css)
    full_width    INTEGER NOT NULL DEFAULT 0,     -- 1 = pages fill the whole window
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,          -- sha256 of the cookie token; raw token never stored
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TEXT NOT NULL
);

-- A chat. Direct chats (is_group = 0) have exactly two members and no name.
CREATE TABLE IF NOT EXISTS conversations (
    id         INTEGER PRIMARY KEY,
    name       TEXT,                      -- NULL = show member names instead
    is_group   INTEGER NOT NULL,
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS conversation_members (
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    last_read_id    INTEGER NOT NULL DEFAULT 0,   -- highest message id this member has seen
    share_devotions INTEGER NOT NULL DEFAULT 0,   -- 1 = this chat can see my devotions (calendar + history)
    share_prayers   INTEGER NOT NULL DEFAULT 0,   -- 1 = this chat can see my prayer list
    joined_at       TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (conversation_id, user_id)
);

CREATE TABLE IF NOT EXISTS devotions (
    id             INTEGER PRIMARY KEY,
    user_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    entry_date     TEXT NOT NULL,         -- YYYY-MM-DD in the writer's local time (travel-friendly)
    scripture      TEXT NOT NULL DEFAULT '',
    observations   TEXT NOT NULL DEFAULT '',
    interpretation TEXT NOT NULL DEFAULT '',
    application    TEXT NOT NULL DEFAULT '',
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (user_id, entry_date)
);

-- kind: 'text' | 'devotion' | 'system'
-- A devotion message points at the live devotion, so later edits show up in the chat.
-- It is only shown while the author still has share_devotions on for that chat.
CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    sender_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind            TEXT NOT NULL,
    body            TEXT NOT NULL DEFAULT '',
    devotion_id     INTEGER REFERENCES devotions(id) ON DELETE SET NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS messages_by_conversation ON messages (conversation_id, id);

CREATE TABLE IF NOT EXISTS prayers (
    id          INTEGER PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title       TEXT NOT NULL,
    body        TEXT NOT NULL DEFAULT '',
    answered_at TEXT,                     -- NULL = still praying
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

SCHEMA_VERSION = 4


def columns(conn, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def migrate(conn):
    """Upgrade an existing database in place, one version step at a time.

    PRAGMA user_version records which version the file is at. Version 2 (chats) never set it,
    so 0 means "version 2, or brand new". A brand-new file has no tables, so every step skips.
    """
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}

    # v3: one share toggle per chat replaces prayer_list_shares
    if version < 3 and "conversation_members" in tables:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(conversation_members)")}
        if "share_mine" not in cols:
            conn.execute("ALTER TABLE conversation_members ADD COLUMN share_mine INTEGER NOT NULL DEFAULT 0")
        if "prayer_list_shares" in tables:
            # Anyone who had shared their prayer list into a chat keeps sharing there.
            conn.execute("""UPDATE conversation_members SET share_mine = 1
                            WHERE (conversation_id, user_id) IN
                                  (SELECT conversation_id, owner_id FROM prayer_list_shares)""")
            conn.execute("DROP TABLE prayer_list_shares")
        conn.execute("DELETE FROM messages WHERE kind = 'prayer_list'")

    # v4: separate toggles for devotions and prayers; per-user display preferences
    if version < 4 and "conversation_members" in tables:
        cols = columns(conn, "conversation_members")
        for col in ("share_devotions", "share_prayers"):
            if col not in cols:
                conn.execute(f"ALTER TABLE conversation_members ADD COLUMN {col} INTEGER NOT NULL DEFAULT 0")
        if "share_mine" in cols:
            # Whoever was sharing "everything" keeps sharing both.
            conn.execute("UPDATE conversation_members SET share_devotions = share_mine, share_prayers = share_mine")
            try:
                conn.execute("ALTER TABLE conversation_members DROP COLUMN share_mine")
            except sqlite3.OperationalError:
                pass  # SQLite older than 3.35 can't drop columns; the unused column is harmless
    if version < 4 and "users" in tables:
        cols = columns(conn, "users")
        if "theme" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN theme TEXT NOT NULL DEFAULT 'warm'")
        if "full_width" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN full_width INTEGER NOT NULL DEFAULT 0")

    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init():
    DB_PATH.parent.mkdir(exist_ok=True)
    with connect() as conn:
        cols = columns(conn, "devotions")
        if cols and "observations" not in cols:
            raise SystemExit(
                "data/devotion.db was made by an older version of this app.\n"
                "Delete the data folder and start again (this erases your test accounts).")
        conn.execute("PRAGMA journal_mode = WAL")
        migrate(conn)
        conn.executescript(SCHEMA)
