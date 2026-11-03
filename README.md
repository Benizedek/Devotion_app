# Daily Bread — devotion & prayer sharing (MVP)

Built the same way as the self-hosted BFE stack: **plain HTML/CSS/JS + Python standard library + SQLite**.
No pip installs, no npm, no framework updates to chase.

## Run it

```
python3 server.py
```
Open http://127.0.0.1:8000, create an account, and you're in. The database is created at `data/devotion.db` on first run.

Needs Python 3.11+ (uses `Path.is_relative_to`, `str.removeprefix`, `X | None` types).

## How the pieces fit

```
browser ──fetch JSON──▶ server.py ──▶ api.py ──▶ db.py (SQLite)
   ▲                       │            │
   └── static/*.html/js ◀──┘          auth.py (passwords + sessions)
```

| File | Job |
|---|---|
| `server.py` | HTTP plumbing: routing, JSON in/out, cookies, static files, security headers. No business rules. |
| `api.py` | **All business logic.** Every endpoint is one function; `ROUTES` at the bottom is the full API map. |
| `auth.py` | PBKDF2-SHA256 password hashing (600k iterations), random session tokens stored only as SHA-256 hashes, 30-day cookies. |
| `db.py` | Schema only — tables and constraints, no triggers or logic. |
| `static/common.js` | `api()` fetch wrapper, `el()` safe DOM builder, nav header, reusable share control. |
| `static/<page>.js` | One script per page. |

## Data model

- **users**, **sessions**
- **conversations** + **conversation_members**: chats. `is_group = 0` is a 1-on-1 chat (reused, never duplicated). In groups anyone can add people; only the creator (`created_by`) can remove them, and the role passes on if they leave. `last_read_id` drives unread badges.
- **conversation_members.share_mine**: the per-chat Settings toggle. When on, that chat sees your prayer list live and each day's devotion is posted there on its first save. When off, your devotion cards in that chat are hidden and your prayers disappear from their "Praying for others".
- **messages**: `kind` is `text`, `devotion` or `system` ("Ben added Grace"). A devotion message points at the live devotion, so edits show up in the chat.
- **devotions**: one per user per day, with Scripture + Observations / Interpretation / Application. Only *today's* devotion can be saved or deleted (checked in `require_editable`); past days are read-only. `entry_date` is the writer's *local* date, so travelling doesn't shift days.
- **prayers**: `answered_at` NULL means still praying.

Access is checked on every request: you only see chats you're a member of.

**Upgrading the database:** `db.migrate()` upgrades an existing `data/devotion.db` in place and records the version in `PRAGMA user_version`. When you change the schema, add a step there instead of deleting the data folder.

Chats update by polling (open chat every 4s, chat list every 10s). That's simple and fine for small groups; WebSockets would be the upgrade later.

## Security choices worth knowing

- **XSS:** the frontend never uses `innerHTML`; all user text goes through `textContent` via `el()`. A strict CSP (`default-src 'self'`) also blocks inline scripts/styles.
- **CSRF:** cookies are `SameSite=Lax` *and* every write must be `Content-Type: application/json`, which a cross-site HTML form can't send.
- **Login timing:** a missing username still runs a full password hash, so attackers can't tell which usernames exist by response time.
- **Path traversal:** static paths are resolved and must stay inside `static/`.

## Deploying (Vultr + Nginx + Cloudflare)

1. Run `server.py` under systemd with `SECURE_COOKIES=1` (and optionally `HOST`/`PORT`).
2. Nginx terminates HTTPS and `proxy_pass`es to `127.0.0.1:8000`.
3. Back up `data/devotion.db` (e.g. nightly `sqlite3 devotion.db ".backup ..."`).

## Not in the MVP yet (good next steps)

- Login rate limiting (do it in Nginx with `limit_req`, or a small counter table)
- Password reset (needs email)
- Push/email notifications for new messages
- "I prayed for this" reactions on prayers and devotions
- Group admin tools (rename, remove member)
- Expired-session cleanup job
