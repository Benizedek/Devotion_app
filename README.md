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
- **user_groups** + **group_members** — join by invite code
- **devotions** — one per user per day (`UNIQUE(user_id, entry_date)`); `entry_date` is the writer's *local* date so travel across time zones doesn't break streaks
- **devotion_shares** — each devotion shared individually, to a user *or* a group
- **prayers** — `answered_at` NULL means still praying
- **prayer_list_shares** — the *whole list* is shared, so viewers always read the live table (the Prayer list page re-fetches every 30s and when the tab regains focus)

Group visibility is checked at read time: leave a group and its shared content disappears for you.

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
- Notifications when someone shares with you / a prayer is answered
- Comments or "I prayed for this" on shared prayers
- Group admin tools (remove member, rotate invite code)
- Expired-session cleanup job
