"""Older database files must upgrade in place without losing anyone's data or sharing choices."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from app import config, db

# The tables as they were in version 3 (one "share_mine" switch, no display preferences).
V3_SCHEMA = """
CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    display_name TEXT NOT NULL, password_hash TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE TABLE conversations (id INTEGER PRIMARY KEY, name TEXT, is_group INTEGER NOT NULL,
    created_by INTEGER NOT NULL, created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE TABLE conversation_members (conversation_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
    last_read_id INTEGER NOT NULL DEFAULT 0, share_mine INTEGER NOT NULL DEFAULT 0,
    joined_at TEXT NOT NULL DEFAULT (datetime('now')), PRIMARY KEY (conversation_id, user_id));
CREATE TABLE devotions (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, entry_date TEXT NOT NULL,
    scripture TEXT NOT NULL DEFAULT '', observations TEXT NOT NULL DEFAULT '', interpretation TEXT NOT NULL DEFAULT '',
    application TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')), UNIQUE (user_id, entry_date));
CREATE TABLE messages (id INTEGER PRIMARY KEY, conversation_id INTEGER NOT NULL, sender_id INTEGER NOT NULL,
    kind TEXT NOT NULL, body TEXT NOT NULL DEFAULT '', devotion_id INTEGER, created_at TEXT NOT NULL DEFAULT (datetime('now')));
INSERT INTO users (id, username, display_name, password_hash) VALUES (1, 'ben', 'Ben', 'x'), (2, 'grace', 'Grace', 'x');
INSERT INTO conversations (id, is_group, created_by) VALUES (1, 0, 1);
INSERT INTO conversation_members (conversation_id, user_id, share_mine) VALUES (1, 1, 1), (1, 2, 0);
PRAGMA user_version = 3;
"""


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        config.DB_PATH = Path(self._tmp.name) / "old.db"

    def tearDown(self):
        self._tmp.cleanup()

    def test_v3_to_current(self):
        with sqlite3.connect(config.DB_PATH) as conn:
            conn.executescript(V3_SCHEMA)
        db.init()
        conn = sqlite3.connect(config.DB_PATH)
        self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], db.migrations.SCHEMA_VERSION)
        rows = conn.execute("SELECT user_id, share_devotions, share_prayers FROM conversation_members ORDER BY user_id").fetchall()
        self.assertEqual(rows, [(1, 1, 1), (2, 0, 0)])                 # "share everything" became both switches
        self.assertNotIn("share_mine", {r[1] for r in conn.execute("PRAGMA table_info(conversation_members)")})
        self.assertEqual(conn.execute("SELECT theme, full_width FROM users WHERE id = 1").fetchone(), ("warm", 0))
        self.assertEqual(conn.execute("SELECT username FROM users ORDER BY id").fetchall(), [("ben",), ("grace",)])
        conn.close()

    def test_fresh_database(self):
        db.init()
        db.init()                                                         # safe to run twice
        conn = sqlite3.connect(config.DB_PATH)
        self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], db.migrations.SCHEMA_VERSION)
        conn.close()
