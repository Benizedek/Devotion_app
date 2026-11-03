"""API handlers. Every business rule lives here, not in the database.

Each handler receives (conn, user, args, body, query) and returns a JSON-able value.
Raise ApiError for anything the client did wrong.
"""
import re
import secrets
import sqlite3
from datetime import date, timedelta

import auth


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


# ---------- small validators ----------
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.]{3,30}$")
MAX_TEXT = 20_000


def text(body: dict, key: str, *, required=False, max_len=MAX_TEXT) -> str:
    value = body.get(key, "")
    if not isinstance(value, str):
        raise ApiError(400, f"{key} must be text")
    value = value.strip()
    if required and not value:
        raise ApiError(400, f"{key} is required")
    if len(value) > max_len:
        raise ApiError(400, f"{key} is too long (max {max_len} characters)")
    return value


def parse_date(value: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except (TypeError, ValueError):
        raise ApiError(400, "Date must be YYYY-MM-DD")


def my_group_ids(conn, user_id: int) -> list[int]:
    return [r[0] for r in conn.execute("SELECT group_id FROM group_members WHERE user_id = ?", (user_id,))]


def resolve_recipient(conn, user, body) -> tuple[int | None, int | None]:
    """Turn {"username": ...} or {"group_id": ...} into (user_id, group_id)."""
    if body.get("username"):
        row = conn.execute("SELECT id FROM users WHERE username = ?", (str(body["username"]).strip(),)).fetchone()
        if row is None:
            raise ApiError(404, "No user with that username")
        if row["id"] == user["id"]:
            raise ApiError(400, "You can't share with yourself")
        return row["id"], None
    if body.get("group_id") is not None:
        try:
            group_id = int(body["group_id"])
        except (TypeError, ValueError):
            raise ApiError(400, "Invalid group")
        if group_id not in my_group_ids(conn, user["id"]):
            raise ApiError(403, "You can only share with groups you belong to")
        return None, group_id
    raise ApiError(400, "Choose a person or a group to share with")


SHARE_LABEL_SQL = """
    COALESCE(u.display_name || ' (@' || u.username || ')', 'Group: ' || g.name) AS label
"""


# ---------- accounts ----------
def register(conn, user, args, body, query):
    username = text(body, "username", required=True, max_len=30)
    if not USERNAME_RE.match(username):
        raise ApiError(400, "Username: 3–30 letters, numbers, _ or .")
    display_name = text(body, "display_name", required=True, max_len=60)
    password = body.get("password", "")
    if not isinstance(password, str) or len(password) < 10:
        raise ApiError(400, "Password must be at least 10 characters")
    try:
        cur = conn.execute("INSERT INTO users (username, display_name, password_hash) VALUES (?, ?, ?)",
                           (username, display_name, auth.hash_password(password)))
    except sqlite3.IntegrityError:
        raise ApiError(409, "That username is taken")
    token = auth.create_session(conn, cur.lastrowid)
    return {"ok": True, "_set_session": token}


def login(conn, user, args, body, query):
    username = text(body, "username", required=True, max_len=30)
    password = body.get("password", "")
    row = conn.execute("SELECT id, password_hash FROM users WHERE username = ?", (username,)).fetchone()
    stored = row["password_hash"] if row else auth.DUMMY_HASH
    if not auth.verify_password(str(password), stored) or row is None:
        raise ApiError(401, "Wrong username or password")
    token = auth.create_session(conn, row["id"])
    return {"ok": True, "_set_session": token}


def logout(conn, user, args, body, query):
    return {"ok": True, "_clear_session": True}


def me(conn, user, args, body, query):
    return user


# ---------- devotions ----------
def devotions_for_month(conn, user, args, body, query):
    month = query.get("month", "")
    if not re.fullmatch(r"\d{4}-\d{2}", month):
        raise ApiError(400, "month must be YYYY-MM")
    rows = conn.execute(
        """SELECT entry_date, title FROM devotions
           WHERE user_id = ? AND entry_date LIKE ? ORDER BY entry_date""",
        (user["id"], month + "-%"),
    ).fetchall()
    return [dict(r) for r in rows]


def get_devotion(conn, user, args, body, query):
    entry_date = parse_date(args[0])
    row = conn.execute(
        "SELECT id, entry_date, title, scripture, body, updated_at FROM devotions WHERE user_id = ? AND entry_date = ?",
        (user["id"], entry_date),
    ).fetchone()
    if row is None:
        return None
    shares = conn.execute(
        f"""SELECT s.id, {SHARE_LABEL_SQL} FROM devotion_shares s
            LEFT JOIN users u ON u.id = s.shared_with_user_id
            LEFT JOIN user_groups g ON g.id = s.shared_with_group_id
            WHERE s.devotion_id = ? ORDER BY s.id""",
        (row["id"],),
    ).fetchall()
    return {**dict(row), "shares": [dict(s) for s in shares]}


def save_devotion(conn, user, args, body, query):
    entry_date = parse_date(args[0])
    if date.fromisoformat(entry_date) > date.today() + timedelta(days=1):
        raise ApiError(400, "Can't write a devotion for a future date")
    title = text(body, "title", max_len=200)
    scripture = text(body, "scripture", max_len=300)
    content = text(body, "body", required=True)
    conn.execute(
        """INSERT INTO devotions (user_id, entry_date, title, scripture, body) VALUES (?, ?, ?, ?, ?)
           ON CONFLICT (user_id, entry_date) DO UPDATE SET
             title = excluded.title, scripture = excluded.scripture,
             body = excluded.body, updated_at = datetime('now')""",
        (user["id"], entry_date, title, scripture, content),
    )
    return get_devotion(conn, user, [entry_date], body, query)


def delete_devotion(conn, user, args, body, query):
    entry_date = parse_date(args[0])
    conn.execute("DELETE FROM devotions WHERE user_id = ? AND entry_date = ?", (user["id"], entry_date))
    return {"ok": True}


def share_devotion(conn, user, args, body, query):
    entry_date = parse_date(args[0])
    row = conn.execute("SELECT id FROM devotions WHERE user_id = ? AND entry_date = ?",
                       (user["id"], entry_date)).fetchone()
    if row is None:
        raise ApiError(404, "Save the devotion before sharing it")
    to_user, to_group = resolve_recipient(conn, user, body)
    exists = conn.execute(
        """SELECT 1 FROM devotion_shares WHERE devotion_id = ?
           AND shared_with_user_id IS ? AND shared_with_group_id IS ?""",
        (row["id"], to_user, to_group),
    ).fetchone()
    if not exists:
        conn.execute("INSERT INTO devotion_shares (devotion_id, shared_with_user_id, shared_with_group_id) VALUES (?, ?, ?)",
                     (row["id"], to_user, to_group))
    return get_devotion(conn, user, [entry_date], body, query)


def unshare_devotion(conn, user, args, body, query):
    share_id = int(args[0])
    # Only the devotion's author can remove its shares.
    conn.execute(
        """DELETE FROM devotion_shares WHERE id = ? AND devotion_id IN
           (SELECT id FROM devotions WHERE user_id = ?)""",
        (share_id, user["id"]),
    )
    return {"ok": True}


def devotion_stats(conn, user, args, body, query):
    """Streaks are computed from the client's 'today' so they're right in any time zone."""
    today = date.fromisoformat(parse_date(query.get("today", "")))
    dates = {date.fromisoformat(r[0]) for r in
             conn.execute("SELECT entry_date FROM devotions WHERE user_id = ?", (user["id"],))}

    # Current streak: counts back from today, or from yesterday if today isn't written yet.
    day = today if today in dates else today - timedelta(days=1)
    current = 0
    while day in dates:
        current += 1
        day -= timedelta(days=1)

    longest = run = 0
    prev = None
    for d in sorted(dates):
        run = run + 1 if prev and d - prev == timedelta(days=1) else 1
        longest = max(longest, run)
        prev = d

    last_30 = sum(1 for d in dates if today - timedelta(days=29) <= d <= today)
    return {"current_streak": current, "longest_streak": longest,
            "last_30_days": last_30, "total": len(dates)}


def shared_devotions(conn, user, args, body, query):
    groups = my_group_ids(conn, user["id"])
    placeholders = ",".join("?" * len(groups)) or "NULL"
    rows = conn.execute(
        f"""SELECT d.id, d.entry_date, d.title, d.scripture, d.body, d.updated_at,
                   a.display_name AS author, a.username AS author_username,
                   GROUP_CONCAT(COALESCE(g.name, 'you directly'), ', ') AS via
            FROM devotion_shares s
            JOIN devotions d ON d.id = s.devotion_id
            JOIN users a ON a.id = d.user_id
            LEFT JOIN user_groups g ON g.id = s.shared_with_group_id
            WHERE d.user_id != ?
              AND (s.shared_with_user_id = ? OR s.shared_with_group_id IN ({placeholders}))
            GROUP BY d.id
            ORDER BY d.entry_date DESC, d.updated_at DESC
            LIMIT 100""",
        (user["id"], user["id"], *groups),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------- prayers ----------
def list_prayers(conn, user, args, body, query):
    rows = conn.execute(
        """SELECT id, title, body, answered_at, created_at, updated_at FROM prayers
           WHERE user_id = ? ORDER BY answered_at IS NOT NULL, updated_at DESC""",
        (user["id"],),
    ).fetchall()
    return [dict(r) for r in rows]


def add_prayer(conn, user, args, body, query):
    title = text(body, "title", required=True, max_len=200)
    details = text(body, "body", max_len=5000)
    conn.execute("INSERT INTO prayers (user_id, title, body) VALUES (?, ?, ?)", (user["id"], title, details))
    return list_prayers(conn, user, args, body, query)


def update_prayer(conn, user, args, body, query):
    prayer_id = int(args[0])
    row = conn.execute("SELECT * FROM prayers WHERE id = ? AND user_id = ?", (prayer_id, user["id"])).fetchone()
    if row is None:
        raise ApiError(404, "Prayer not found")
    title = text(body, "title", required=True, max_len=200) if "title" in body else row["title"]
    details = text(body, "body", max_len=5000) if "body" in body else row["body"]
    answered_at = row["answered_at"]
    if "answered" in body:
        # Client sends its local date so "answered on" matches the user's day, wherever they are.
        answered_on = parse_date(body["today"]) if body.get("today") else date.today().isoformat()
        answered_at = (answered_at or answered_on) if body["answered"] else None
    conn.execute(
        "UPDATE prayers SET title = ?, body = ?, answered_at = ?, updated_at = datetime('now') WHERE id = ?",
        (title, details, answered_at, prayer_id),
    )
    return list_prayers(conn, user, args, body, query)


def delete_prayer(conn, user, args, body, query):
    conn.execute("DELETE FROM prayers WHERE id = ? AND user_id = ?", (int(args[0]), user["id"]))
    return list_prayers(conn, user, args, body, query)


def list_prayer_shares(conn, user, args, body, query):
    rows = conn.execute(
        f"""SELECT s.id, {SHARE_LABEL_SQL} FROM prayer_list_shares s
            LEFT JOIN users u ON u.id = s.shared_with_user_id
            LEFT JOIN user_groups g ON g.id = s.shared_with_group_id
            WHERE s.owner_id = ? ORDER BY s.id""",
        (user["id"],),
    ).fetchall()
    return [dict(r) for r in rows]


def add_prayer_share(conn, user, args, body, query):
    to_user, to_group = resolve_recipient(conn, user, body)
    exists = conn.execute(
        """SELECT 1 FROM prayer_list_shares WHERE owner_id = ?
           AND shared_with_user_id IS ? AND shared_with_group_id IS ?""",
        (user["id"], to_user, to_group),
    ).fetchone()
    if not exists:
        conn.execute("INSERT INTO prayer_list_shares (owner_id, shared_with_user_id, shared_with_group_id) VALUES (?, ?, ?)",
                     (user["id"], to_user, to_group))
    return list_prayer_shares(conn, user, args, body, query)


def remove_prayer_share(conn, user, args, body, query):
    conn.execute("DELETE FROM prayer_list_shares WHERE id = ? AND owner_id = ?", (int(args[0]), user["id"]))
    return list_prayer_shares(conn, user, args, body, query)


def shared_prayer_lists(conn, user, args, body, query):
    """Read live from the prayers table, so viewers always see the current list."""
    groups = my_group_ids(conn, user["id"])
    placeholders = ",".join("?" * len(groups)) or "NULL"
    owners = conn.execute(
        f"""SELECT DISTINCT u.id, u.display_name, u.username FROM prayer_list_shares s
            JOIN users u ON u.id = s.owner_id
            WHERE s.owner_id != ?
              AND (s.shared_with_user_id = ? OR s.shared_with_group_id IN ({placeholders}))
            ORDER BY u.display_name""",
        (user["id"], user["id"], *groups),
    ).fetchall()
    result = []
    for owner in owners:
        prayers = conn.execute(
            """SELECT id, title, body, answered_at, updated_at FROM prayers
               WHERE user_id = ? ORDER BY answered_at IS NOT NULL, updated_at DESC""",
            (owner["id"],),
        ).fetchall()
        result.append({"owner": owner["display_name"], "username": owner["username"],
                       "prayers": [dict(p) for p in prayers]})
    return result


# ---------- groups ----------
def list_groups(conn, user, args, body, query):
    groups = conn.execute(
        """SELECT g.id, g.name, g.invite_code, g.owner_id = ? AS is_owner FROM user_groups g
           JOIN group_members m ON m.group_id = g.id WHERE m.user_id = ? ORDER BY g.name""",
        (user["id"], user["id"]),
    ).fetchall()
    result = []
    for g in groups:
        members = conn.execute(
            """SELECT u.display_name, u.username FROM group_members m JOIN users u ON u.id = m.user_id
               WHERE m.group_id = ? ORDER BY u.display_name""",
            (g["id"],),
        ).fetchall()
        result.append({**dict(g), "is_owner": bool(g["is_owner"]), "members": [dict(m) for m in members]})
    return result


def create_group(conn, user, args, body, query):
    name = text(body, "name", required=True, max_len=80)
    code = secrets.token_urlsafe(6)
    cur = conn.execute("INSERT INTO user_groups (name, invite_code, owner_id) VALUES (?, ?, ?)",
                       (name, code, user["id"]))
    conn.execute("INSERT INTO group_members (group_id, user_id) VALUES (?, ?)", (cur.lastrowid, user["id"]))
    return list_groups(conn, user, args, body, query)


def join_group(conn, user, args, body, query):
    code = text(body, "code", required=True, max_len=40)
    row = conn.execute("SELECT id FROM user_groups WHERE invite_code = ?", (code,)).fetchone()
    if row is None:
        raise ApiError(404, "No group with that invite code")
    conn.execute("INSERT OR IGNORE INTO group_members (group_id, user_id) VALUES (?, ?)", (row["id"], user["id"]))
    return list_groups(conn, user, args, body, query)


def leave_group(conn, user, args, body, query):
    conn.execute("DELETE FROM group_members WHERE group_id = ? AND user_id = ?", (int(args[0]), user["id"]))
    return list_groups(conn, user, args, body, query)


# ---------- routing table: (method, path regex, handler, login required) ----------
ROUTES = [
    ("POST",   r"/api/register",                   register,            False),
    ("POST",   r"/api/login",                      login,               False),
    ("POST",   r"/api/logout",                     logout,              False),
    ("GET",    r"/api/me",                         me,                  True),

    ("GET",    r"/api/devotions",                  devotions_for_month, True),
    ("GET",    r"/api/devotions/stats",            devotion_stats,      True),
    ("GET",    r"/api/devotions/shared",           shared_devotions,    True),
    ("GET",    r"/api/devotions/([\d-]+)",         get_devotion,        True),
    ("PUT",    r"/api/devotions/([\d-]+)",         save_devotion,       True),
    ("DELETE", r"/api/devotions/([\d-]+)",         delete_devotion,     True),
    ("POST",   r"/api/devotions/([\d-]+)/shares",  share_devotion,      True),
    ("DELETE", r"/api/devotion-shares/(\d+)",      unshare_devotion,    True),

    ("GET",    r"/api/prayers",                    list_prayers,        True),
    ("POST",   r"/api/prayers",                    add_prayer,          True),
    ("GET",    r"/api/prayers/shared",             shared_prayer_lists, True),
    ("PATCH",  r"/api/prayers/(\d+)",              update_prayer,       True),
    ("DELETE", r"/api/prayers/(\d+)",              delete_prayer,       True),
    ("GET",    r"/api/prayer-shares",              list_prayer_shares,  True),
    ("POST",   r"/api/prayer-shares",              add_prayer_share,    True),
    ("DELETE", r"/api/prayer-shares/(\d+)",        remove_prayer_share, True),

    ("GET",    r"/api/groups",                     list_groups,         True),
    ("POST",   r"/api/groups",                     create_group,        True),
    ("POST",   r"/api/groups/join",                join_group,          True),
    ("POST",   r"/api/groups/(\d+)/leave",         leave_group,         True),
]
ROUTES = [(m, re.compile(p + "$"), h, a) for m, p, h, a in ROUTES]
