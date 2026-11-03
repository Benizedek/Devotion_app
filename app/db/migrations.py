"""Upgrade an existing database file in place, one version step at a time.

When you change schema.sql in a way that affects existing tables (new column, renamed
column, dropped table), bump SCHEMA_VERSION and add a step below.
"""
import sqlite3


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
