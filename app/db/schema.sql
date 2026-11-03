-- Database structure only. All rules live in Python (app/api/).
-- Run on every start with CREATE ... IF NOT EXISTS, so it's safe to run repeatedly.
-- To change an existing table, add a step in migrations.py as well.

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
