"""Sign-up, login, the current user, display preferences, and people search."""
import re
import sqlite3

from .. import auth
from .validation import ApiError, text


USERNAME_RE = re.compile(r"^[A-Za-z0-9_.]{3,30}$")


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


THEMES = ("warm", "sage", "ocean", "plum", "slate")


def me(conn, user, args, body, query):
    prefs = conn.execute("SELECT theme, full_width FROM users WHERE id = ?", (user["id"],)).fetchone()
    return {**user, "theme": prefs["theme"], "full_width": bool(prefs["full_width"])}


def update_preferences(conn, user, args, body, query):
    if "theme" in body:
        if body["theme"] not in THEMES:
            raise ApiError(400, "Unknown color theme")
        conn.execute("UPDATE users SET theme = ? WHERE id = ?", (body["theme"], user["id"]))
    if "full_width" in body:
        if not isinstance(body["full_width"], bool):
            raise ApiError(400, "full_width must be true or false")
        conn.execute("UPDATE users SET full_width = ? WHERE id = ?", (int(body["full_width"]), user["id"]))
    return me(conn, user, args, body, query)


def search_users(conn, user, args, body, query):
    q = query.get("q", "").strip()
    if len(q) < 2:
        return []
    # Escape LIKE wildcards so searching "a_b" means a literal underscore.
    like = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    rows = conn.execute(
        r"""SELECT id, username, display_name FROM users
            WHERE id != ? AND (username LIKE ? ESCAPE '\' OR display_name LIKE ? ESCAPE '\')
            ORDER BY display_name LIMIT 20""",
        (user["id"], like, like),
    ).fetchall()
    return [dict(r) for r in rows]


# (method, path pattern, handler, login required)
ROUTES = [
    ("POST",   r"/api/register", register, False),
    ("POST",   r"/api/login", login, False),
    ("POST",   r"/api/logout", logout, False),
    ("GET",    r"/api/me", me, True),
    ("PATCH",  r"/api/me/preferences", update_preferences, True),
    ("GET",    r"/api/users/search", search_users, True),
]
