# Daily Bread — devotion & prayer sharing (MVP)

Built the same way as the self-hosted BFE stack: **plain HTML/CSS/JS + Python standard library + SQLite**.
No pip installs, no npm, no framework updates to chase.

## Run it

```
python3 server.py
```
Open http://127.0.0.1:8000, create an account, and you're in. The database is created at `data/devotion.db` on first run.

Needs Python 3.11+ (uses `Path.is_relative_to`, `str.removeprefix`, `X | None` types).

## Run the tests

```
python -m unittest
```
Run it from the project folder. Each test file starts the real server on a throwaway database, so your `data/` is never touched. Run the tests after every change, before you push.

## Project layout

```
server.py                  start here: `python server.py`
app/                       backend (Python standard library only)
  config.py                settings from environment variables (HOST, PORT, DEVOTION_DB, ...)
  server.py                HTTP plumbing: JSON in/out, cookies, static files, security headers
  router.py                gathers every feature's ROUTES and finds the handler for a request
  auth.py                  password hashing + login sessions
  db/
    schema.sql             the tables (structure only, no logic)
    migrations.py          upgrades older database files in place
    __init__.py            connect() and init()
  api/                     business logic, one module per feature
    accounts.py            sign-up, login, preferences, people search
    chats.py               chats and their members
    messages.py            messages inside a chat
    sharing.py             per-chat devotion / prayer switches, Permissions page
    devotions.py           your devotions (only today is editable)
    prayers.py             your prayer list + lists shared with you
    people.py              someone else's page, limited to what they share
    chat_store.py          helpers shared by chats / messages / sharing
    validation.py          input checks and ApiError
frontend/                  everything the browser loads (served at /static/)
  pages/                   one HTML file per page
  css/                     app.css imports: tokens, base, layout, components, chat, pages
  js/lib/                  shared modules: api, dom, dates, prefs, header, widgets
  js/pages/                one script per page, importing what it needs from js/lib/
tests/                     one test file per feature, plus security and migrations
```

**How a request flows:** the browser calls `/api/...` → `app/server.py` reads the JSON and the session cookie → `app/router.py` picks the handler → the handler in `app/api/<feature>.py` checks the rules and queries SQLite → JSON goes back.

**Which way imports go:** `validation` ← `chat_store` ← `chats` ← `sharing` ← `devotions` ← `messages` / `people`, and `prayers` ← `people`. Nothing imports "upward", so there are no import loops. If you need something from a module further along that chain, move it down into a shared helper instead.

**Adding an endpoint:** write the handler in the feature module, add a row to that module's `ROUTES`, and add a test in `tests/test_<feature>.py`.

**Adding a page:** create `frontend/pages/<name>.html` and `frontend/js/pages/<name>.js`, and add its URL to `PAGES` in `app/server.py`.

## Data model

- **users**, **sessions**
- **conversations** + **conversation_members**: chats. `is_group = 0` is a 1-on-1 chat (reused, never duplicated). In groups anyone can add people; only the creator (`created_by`) can remove them, and the role passes on if they leave. `last_read_id` drives unread badges.
- **conversation_members.share_devotions / share_prayers**: two independent per-chat permissions, set in a chat's Settings or on the Permissions page.
  - Devotions on: that chat's members can open your page (`/person?u=you`) to see your calendar and any devotion, and each day's devotion is posted into the chat on its first save. Off: your devotion cards in that chat are hidden.
  - Prayers on: your *active* prayers appear in their "Praying for others" and on your page.
  - `can_see()` in `app/api/people.py` is the single rule for "may this viewer see that person's X?": true if the owner shares X with any chat the viewer is also in.
- **messages**: `kind` is `text`, `devotion` or `system` ("Ben added Grace"). A devotion message points at the live devotion, so edits show up in the chat.
- **devotions**: one per user per day, with Scripture + Observations / Interpretation / Application. Only *today's* devotion can be saved or deleted (checked in `require_editable`); past days are read-only. `entry_date` is the writer's *local* date, so travelling doesn't shift days.
- **prayers**: `answered_at` NULL means still praying. Answered prayers move to your private archive (`/prayers/answered`) and are never shown to others.
- **users.theme / users.full_width**: display preferences, stored on the account so they follow you across devices.

Access is checked on every request: you only see chats you're a member of.

**Upgrading the database:** `app/db/migrations.py` upgrades an existing `data/devotion.db` in place and records the version in `PRAGMA user_version`. When you change `schema.sql` in a way that affects existing tables, bump `SCHEMA_VERSION` and add a step there instead of deleting the data folder.

Chats update by polling (open chat every 4s, chat list every 10s). That's simple and fine for small groups; WebSockets would be the upgrade later.

## Security choices worth knowing

- **XSS:** the frontend never uses `innerHTML`; all user text goes through `textContent` via `el()`. A strict CSP (`default-src 'self'`) also blocks inline scripts/styles.
- **CSRF:** cookies are `SameSite=Lax` *and* every write must be `Content-Type: application/json`, which a cross-site HTML form can't send.
- **Login timing:** a missing username still runs a full password hash, so attackers can't tell which usernames exist by response time.
- **Path traversal:** static paths are resolved and must stay inside `frontend/`.

## Deploying (Vultr + Nginx + Cloudflare)

1. Run `server.py` under systemd with `SECURE_COOKIES=1` (and optionally `HOST`/`PORT`).
2. Nginx terminates HTTPS and `proxy_pass`es to `127.0.0.1:8000`.
3. Back up `data/devotion.db` (e.g. nightly `sqlite3 devotion.db ".backup ..."`).
