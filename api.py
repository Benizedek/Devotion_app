"""API handlers. Every business rule lives here, not in the database.

Each handler receives (conn, user, args, body, query) and returns a JSON-able value.
Raise ApiError for anything the client did wrong.
"""
import re
import sqlite3
from datetime import date

import auth


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


# ---------- small validators ----------
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.]{3,30}$")
MAX_TEXT = 20_000
MAX_MESSAGE = 4_000
MAX_GROUP_SIZE = 50
DEVOTION_FIELDS = ("observations", "interpretation", "application")


def text(body: dict, key: str, *, required=False, max_len=MAX_TEXT) -> str:
    value = body.get(key, "")
    if value is None:
        value = ""
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


def parse_id(value, what="id") -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ApiError(400, f"Invalid {what}")


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


# ---------- conversations (chats) ----------
def require_member(conn, conv_id: int, user):
    row = conn.execute(
        """SELECT c.id, c.name, c.is_group, c.created_by, m.share_devotions, m.share_prayers FROM conversations c
           JOIN conversation_members m ON m.conversation_id = c.id
           WHERE c.id = ? AND m.user_id = ?""",
        (conv_id, user["id"]),
    ).fetchone()
    if row is None:
        raise ApiError(404, "Chat not found")
    return row


def members_of(conn, conv_id: int) -> list[dict]:
    rows = conn.execute(
        """SELECT u.id, u.display_name, u.username, m.share_devotions, m.share_prayers FROM conversation_members m
           JOIN users u ON u.id = m.user_id WHERE m.conversation_id = ? ORDER BY u.display_name""",
        (conv_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def title_for(conv, members: list[dict], user_id: int) -> str:
    others = [m["display_name"] for m in members if m["id"] != user_id]
    if conv["is_group"]:
        return conv["name"] or ", ".join(others) or "Group"
    return others[0] if others else "Chat"


def clean_user_ids(conn, user, raw) -> list[int]:
    if not isinstance(raw, list) or not raw:
        raise ApiError(400, "Add at least one person")
    ids = []
    for value in raw:
        uid = parse_id(value, "person")
        if uid != user["id"] and uid not in ids:
            ids.append(uid)
    if not ids:
        raise ApiError(400, "Add at least one other person")
    if len(ids) > MAX_GROUP_SIZE:
        raise ApiError(400, f"Groups can have at most {MAX_GROUP_SIZE} people")
    found = conn.execute(f"SELECT COUNT(*) FROM users WHERE id IN ({','.join('?' * len(ids))})", ids).fetchone()[0]
    if found != len(ids):
        raise ApiError(404, "Some of those people don't exist")
    return ids


def post_message(conn, conv_id, sender_id, kind, body="", devotion_id=None):
    cur = conn.execute(
        "INSERT INTO messages (conversation_id, sender_id, kind, body, devotion_id) VALUES (?, ?, ?, ?, ?)",
        (conv_id, sender_id, kind, body, devotion_id),
    )
    return cur.lastrowid


def preview_text(row, user_id: int, is_group: bool) -> str:
    kind = row["kind"]
    if kind == "system":
        return row["body"]
    who = "You" if row["sender_id"] == user_id else row["sender"].split(" ")[0]
    if kind == "devotion":
        return f"{who} shared a devotion"
    return f"{who}: {row['body']}" if (is_group or who == "You") else row["body"]


def list_conversations(conn, user, args, body, query):
    convs = conn.execute(
        """SELECT c.id, c.name, c.is_group, c.created_at, m.last_read_id,
                  (SELECT MAX(id) FROM messages WHERE conversation_id = c.id) AS last_id
           FROM conversations c
           JOIN conversation_members m ON m.conversation_id = c.id AND m.user_id = ?""",
        (user["id"],),
    ).fetchall()
    result = []
    for c in convs:
        members = members_of(conn, c["id"])
        last = None
        if c["last_id"]:
            last = conn.execute(
                """SELECT m.kind, m.body, m.created_at, m.sender_id, u.display_name AS sender
                   FROM messages m JOIN users u ON u.id = m.sender_id WHERE m.id = ?""",
                (c["last_id"],),
            ).fetchone()
        unread = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE conversation_id = ? AND id > ? AND sender_id != ?",
            (c["id"], c["last_read_id"], user["id"]),
        ).fetchone()[0]
        result.append({
            "id": c["id"],
            "title": title_for(c, members, user["id"]),
            "is_group": bool(c["is_group"]),
            "member_count": len(members),
            "preview": preview_text(last, user["id"], bool(c["is_group"])) if last else "",
            "last_at": last["created_at"] if last else c["created_at"],
            "unread": unread,
        })
    result.sort(key=lambda r: r["last_at"], reverse=True)
    return result


def create_conversation(conn, user, args, body, query):
    ids = clean_user_ids(conn, user, body.get("user_ids"))
    name = text(body, "name", max_len=80)
    is_group = len(ids) > 1 or bool(name)

    if not is_group:
        # Reuse the existing 1-on-1 chat instead of making duplicates.
        row = conn.execute(
            """SELECT c.id FROM conversations c
               JOIN conversation_members a ON a.conversation_id = c.id AND a.user_id = ?
               JOIN conversation_members b ON b.conversation_id = c.id AND b.user_id = ?
               WHERE c.is_group = 0""",
            (user["id"], ids[0]),
        ).fetchone()
        if row:
            return {"id": row["id"]}

    cur = conn.execute("INSERT INTO conversations (name, is_group, created_by) VALUES (?, ?, ?)",
                       (name or None, int(is_group), user["id"]))
    conv_id = cur.lastrowid
    conn.executemany("INSERT INTO conversation_members (conversation_id, user_id) VALUES (?, ?)",
                     [(conv_id, uid) for uid in [user["id"], *ids]])
    if is_group:
        post_message(conn, conv_id, user["id"], "system", f"{user['display_name']} created the group")
    return {"id": conv_id}


def get_conversation(conn, user, args, body, query):
    conv = require_member(conn, parse_id(args[0]), user)
    members = members_of(conn, conv["id"])
    for m in members:
        m["share_devotions"] = bool(m["share_devotions"])
        m["share_prayers"] = bool(m["share_prayers"])
        m["is_admin"] = bool(conv["is_group"]) and m["id"] == conv["created_by"]
    return {"id": conv["id"], "title": title_for(conv, members, user["id"]),
            "name": conv["name"], "is_group": bool(conv["is_group"]), "members": members,
            "share_devotions": bool(conv["share_devotions"]),
            "share_prayers": bool(conv["share_prayers"]),
            "is_admin": bool(conv["is_group"]) and conv["created_by"] == user["id"]}


SHARE_SETTINGS = {"share_devotions": "devotions", "share_prayers": "prayer list"}


def update_settings(conn, user, args, body, query):
    """Turn sharing my devotions and/or my prayer list with this chat on or off (independently)."""
    conv = require_member(conn, parse_id(args[0]), user)
    changes = {k: body[k] for k in SHARE_SETTINGS if k in body}
    if not changes:
        raise ApiError(400, "Nothing to change")
    for key, value in changes.items():
        if not isinstance(value, bool):
            raise ApiError(400, f"{key} must be true or false")
        if value == bool(conv[key]):
            continue
        # key comes from SHARE_SETTINGS, never from the client, so it's safe in the SQL text.
        conn.execute(f"UPDATE conversation_members SET {key} = ? WHERE conversation_id = ? AND user_id = ?",
                     (int(value), conv["id"], user["id"]))
        verb = "started" if value else "stopped"
        post_message(conn, conv["id"], user["id"], "system",
                     f"{user['display_name']} {verb} sharing their {SHARE_SETTINGS[key]}")
        if key == "share_devotions" and value and body.get("today"):
            # Post today's devotion right away if it's already written and not here yet.
            post_devotion_if_new(conn, user, conv["id"], parse_date(body["today"]))
    return get_conversation(conn, user, [conv["id"]], body, query)


def list_permissions(conn, user, args, body, query):
    """Every chat I'm in, with my two share settings, for the Permissions page."""
    rows = conn.execute(
        """SELECT c.id, c.name, c.is_group, m.share_devotions, m.share_prayers FROM conversations c
           JOIN conversation_members m ON m.conversation_id = c.id AND m.user_id = ?""",
        (user["id"],),
    ).fetchall()
    result = [{"id": r["id"], "title": title_for(r, members_of(conn, r["id"]), user["id"]),
               "is_group": bool(r["is_group"]),
               "share_devotions": bool(r["share_devotions"]), "share_prayers": bool(r["share_prayers"])}
              for r in rows]
    result.sort(key=lambda r: (not r["is_group"], r["title"].lower()))
    return result


def remove_member(conn, user, args, body, query):
    conv = require_member(conn, parse_id(args[0]), user)
    target = parse_id(args[1], "person")
    if not conv["is_group"]:
        raise ApiError(400, "You can't remove people from a 1-on-1 chat")
    if conv["created_by"] != user["id"]:
        raise ApiError(403, "Only the group's creator can remove people")
    if target == user["id"]:
        raise ApiError(400, "Use Leave group to remove yourself")
    row = conn.execute(
        """SELECT u.display_name FROM conversation_members m JOIN users u ON u.id = m.user_id
           WHERE m.conversation_id = ? AND m.user_id = ?""",
        (conv["id"], target),
    ).fetchone()
    if row is None:
        raise ApiError(404, "That person isn't in this group")
    conn.execute("DELETE FROM conversation_members WHERE conversation_id = ? AND user_id = ?", (conv["id"], target))
    post_message(conn, conv["id"], user["id"], "system", f"{user['display_name']} removed {row['display_name']}")
    return get_conversation(conn, user, [conv["id"]], body, query)


def add_members(conn, user, args, body, query):
    conv = require_member(conn, parse_id(args[0]), user)
    if not conv["is_group"]:
        raise ApiError(400, "Start a new group to chat with more people")
    current = {m["id"] for m in members_of(conn, conv["id"])}
    new_ids = [uid for uid in clean_user_ids(conn, user, body.get("user_ids")) if uid not in current]
    if len(current) + len(new_ids) > MAX_GROUP_SIZE:
        raise ApiError(400, f"Groups can have at most {MAX_GROUP_SIZE} people")
    if new_ids:
        conn.executemany("INSERT INTO conversation_members (conversation_id, user_id) VALUES (?, ?)",
                         [(conv["id"], uid) for uid in new_ids])
        names = [r[0] for r in conn.execute(
            f"SELECT display_name FROM users WHERE id IN ({','.join('?' * len(new_ids))})", new_ids)]
        post_message(conn, conv["id"], user["id"], "system", f"{user['display_name']} added {', '.join(names)}")
    return get_conversation(conn, user, [conv["id"]], body, query)


def leave_conversation(conn, user, args, body, query):
    conv = require_member(conn, parse_id(args[0]), user)
    if not conv["is_group"]:
        raise ApiError(400, "You can only leave group chats")
    conn.execute("DELETE FROM conversation_members WHERE conversation_id = ? AND user_id = ?", (conv["id"], user["id"]))
    next_admin = conn.execute(
        "SELECT user_id FROM conversation_members WHERE conversation_id = ? ORDER BY joined_at, rowid LIMIT 1",
        (conv["id"],),
    ).fetchone()
    if next_admin is None:
        conn.execute("DELETE FROM conversations WHERE id = ?", (conv["id"],))
        return {"ok": True}
    post_message(conn, conv["id"], user["id"], "system", f"{user['display_name']} left the group")
    if conv["created_by"] == user["id"]:
        # Hand the creator role to whoever has been in the group longest.
        conn.execute("UPDATE conversations SET created_by = ? WHERE id = ?", (next_admin["user_id"], conv["id"]))
    return {"ok": True}


# ---------- messages ----------
def format_message(r, user) -> dict:
    msg = {"id": r["id"], "kind": r["kind"], "body": r["body"], "created_at": r["created_at"],
           "sender": r["sender"], "mine": r["sender_id"] == user["id"]}
    if r["kind"] == "devotion":
        # Shown only while the author still shares with this chat (always to the author).
        visible = msg["mine"] or bool(r["author_sharing"])
        msg["devotion_status"] = "deleted" if r["devotion_id"] is None else ("shown" if visible else "hidden")
        msg["devotion"] = None if msg["devotion_status"] != "shown" else {
            "entry_date": r["entry_date"], "scripture": r["scripture"],
            **{f: r[f] for f in DEVOTION_FIELDS}}
    return msg


def list_messages(conn, user, args, body, query):
    conv = require_member(conn, parse_id(args[0]), user)
    after = parse_id(query.get("after", 0), "after")
    rows = conn.execute(
        """SELECT * FROM (
             SELECT m.id, m.kind, m.body, m.created_at, m.sender_id, u.display_name AS sender,
                    m.devotion_id, d.entry_date, d.scripture, d.observations, d.interpretation, d.application,
                    am.share_devotions AS author_sharing
             FROM messages m JOIN users u ON u.id = m.sender_id
             LEFT JOIN devotions d ON d.id = m.devotion_id
             LEFT JOIN conversation_members am ON am.conversation_id = m.conversation_id AND am.user_id = m.sender_id
             WHERE m.conversation_id = ? AND m.id > ?
             ORDER BY m.id DESC LIMIT 200
           ) ORDER BY id""",
        (conv["id"], after),
    ).fetchall()
    if rows:
        conn.execute(
            """UPDATE conversation_members SET last_read_id = MAX(last_read_id, ?)
               WHERE conversation_id = ? AND user_id = ?""",
            (rows[-1]["id"], conv["id"], user["id"]),
        )
    return [format_message(r, user) for r in rows]


def send_message(conn, user, args, body, query):
    conv = require_member(conn, parse_id(args[0]), user)
    content = text(body, "body", required=True, max_len=MAX_MESSAGE)
    return {"id": post_message(conn, conv["id"], user["id"], "text", content)}


def delete_message(conn, user, args, body, query):
    conn.execute("DELETE FROM messages WHERE id = ? AND sender_id = ? AND kind != 'system'",
                 (parse_id(args[0]), user["id"]))
    return {"ok": True}


# ---------- devotions ----------
def devotions_for_month(conn, user, args, body, query):
    month = query.get("month", "")
    if not re.fullmatch(r"\d{4}-\d{2}", month):
        raise ApiError(400, "month must be YYYY-MM")
    rows = conn.execute(
        "SELECT entry_date FROM devotions WHERE user_id = ? AND entry_date LIKE ? ORDER BY entry_date",
        (user["id"], month + "-%"),
    ).fetchall()
    return [r["entry_date"] for r in rows]


def get_devotion(conn, user, args, body, query):
    entry_date = parse_date(args[0])
    row = conn.execute(
        """SELECT id, entry_date, scripture, observations, interpretation, application, updated_at
           FROM devotions WHERE user_id = ? AND entry_date = ?""",
        (user["id"], entry_date),
    ).fetchone()
    if row is None:
        return None
    return dict(row)


def sharing_chats(conn, user) -> list[dict]:
    """Chats I've turned devotion sharing on for."""
    rows = conn.execute(
        """SELECT c.id, c.name, c.is_group FROM conversations c
           JOIN conversation_members m ON m.conversation_id = c.id
           WHERE m.user_id = ? AND m.share_devotions = 1""",
        (user["id"],),
    ).fetchall()
    return [{"id": r["id"], "title": title_for(r, members_of(conn, r["id"]), user["id"])} for r in rows]


def visible_to(conn, user, args, body, query):
    return sharing_chats(conn, user)


def require_editable(body, entry_date: str):
    """Only today's devotion can be written or changed; every other day is read-only.

    'Today' comes from the client (its local date, so travel works). It must match the
    devotion's date and be within a day of the server's date, which covers every time zone.
    """
    today = parse_date(body.get("today") or "")
    if entry_date != today or abs((date.fromisoformat(today) - date.today()).days) > 1:
        raise ApiError(403, "Only today's devotion can be edited")


def post_devotion_if_new(conn, user, conv_id: int, entry_date: str):
    row = conn.execute("SELECT id FROM devotions WHERE user_id = ? AND entry_date = ?",
                       (user["id"], entry_date)).fetchone()
    if row is None:
        return
    already = conn.execute("SELECT 1 FROM messages WHERE conversation_id = ? AND devotion_id = ?",
                           (conv_id, row["id"])).fetchone()
    if not already:
        post_message(conn, conv_id, user["id"], "devotion", devotion_id=row["id"])


def save_devotion(conn, user, args, body, query):
    entry_date = parse_date(args[0])
    require_editable(body, entry_date)
    scripture = text(body, "scripture", max_len=300)
    fields = {f: text(body, f) for f in DEVOTION_FIELDS}
    if not any(fields.values()):
        raise ApiError(400, "Write at least one of Observations, Interpretation or Application")
    conn.execute(
        """INSERT INTO devotions (user_id, entry_date, scripture, observations, interpretation, application)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT (user_id, entry_date) DO UPDATE SET
             scripture = excluded.scripture, observations = excluded.observations,
             interpretation = excluded.interpretation, application = excluded.application,
             updated_at = datetime('now')""",
        (user["id"], entry_date, scripture, *fields.values()),
    )
    # First save of the day posts it to every chat I share with; later edits show up live.
    for chat in sharing_chats(conn, user):
        post_devotion_if_new(conn, user, chat["id"], entry_date)
    return get_devotion(conn, user, [entry_date], body, query)


def delete_devotion(conn, user, args, body, query):
    entry_date = parse_date(args[0])
    require_editable(body, entry_date)
    conn.execute("DELETE FROM devotions WHERE user_id = ? AND entry_date = ?", (user["id"], entry_date))
    return {"ok": True}


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
    prayer_id = parse_id(args[0])
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
    conn.execute("DELETE FROM prayers WHERE id = ? AND user_id = ?", (parse_id(args[0]), user["id"]))
    return list_prayers(conn, user, args, body, query)


def shared_prayer_lists(conn, user, args, body, query):
    """Prayer lists of people who share prayers with a chat I'm in. Read live from the prayers table.

    'via' lists the chats each list reaches me through, so the page can filter by group or person.
    """
    owners = conn.execute(
        """SELECT u.id, u.display_name, u.username, GROUP_CONCAT(theirs.conversation_id) AS via
           FROM conversation_members theirs
           JOIN conversation_members mine ON mine.conversation_id = theirs.conversation_id AND mine.user_id = ?
           JOIN users u ON u.id = theirs.user_id
           WHERE theirs.share_prayers = 1 AND theirs.user_id != ?
           GROUP BY u.id ORDER BY u.display_name""",
        (user["id"], user["id"]),
    ).fetchall()
    return [{"owner": o["display_name"], "username": o["username"],
             "via": [int(v) for v in o["via"].split(",")],
             "prayers": active_prayers(conn, o["id"])} for o in owners]


def active_prayers(conn, user_id: int) -> list[dict]:
    """Answered prayers live in the owner's archive, so others only see ones still being prayed for."""
    rows = conn.execute(
        """SELECT id, title, body, updated_at FROM prayers
           WHERE user_id = ? AND answered_at IS NULL ORDER BY updated_at DESC""",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------- another person's page ----------
def can_see(conn, viewer_id: int, owner_id: int, what: str) -> bool:
    """True if the owner shares `what` with any chat the viewer is also in."""
    if viewer_id == owner_id:
        return True
    column = {"devotions": "share_devotions", "prayers": "share_prayers"}[what]   # whitelist, never client text
    return conn.execute(
        f"""SELECT 1 FROM conversation_members theirs
            JOIN conversation_members mine ON mine.conversation_id = theirs.conversation_id AND mine.user_id = ?
            WHERE theirs.user_id = ? AND theirs.{column} = 1 LIMIT 1""",
        (viewer_id, owner_id),
    ).fetchone() is not None


def find_person(conn, username: str):
    row = conn.execute("SELECT id, username, display_name FROM users WHERE username = ?", (username,)).fetchone()
    if row is None:
        raise ApiError(404, "No one with that username")
    return row


def person_profile(conn, user, args, body, query):
    p = find_person(conn, args[0])
    return {"username": p["username"], "display_name": p["display_name"], "is_me": p["id"] == user["id"],
            "can_see_devotions": can_see(conn, user["id"], p["id"], "devotions"),
            "can_see_prayers": can_see(conn, user["id"], p["id"], "prayers")}


def person_devotion_month(conn, user, args, body, query):
    p = find_person(conn, args[0])
    if not can_see(conn, user["id"], p["id"], "devotions"):
        raise ApiError(403, f"{p['display_name']} isn't sharing devotions with you")
    return devotions_for_month(conn, {"id": p["id"]}, args, body, query)


def person_devotion(conn, user, args, body, query):
    p = find_person(conn, args[0])
    if not can_see(conn, user["id"], p["id"], "devotions"):
        raise ApiError(403, f"{p['display_name']} isn't sharing devotions with you")
    return get_devotion(conn, {"id": p["id"]}, [args[1]], body, query)


def person_prayers(conn, user, args, body, query):
    p = find_person(conn, args[0])
    if not can_see(conn, user["id"], p["id"], "prayers"):
        raise ApiError(403, f"{p['display_name']} isn't sharing prayers with you")
    return active_prayers(conn, p["id"])


# ---------- routing table: (method, path regex, handler, login required) ----------
ROUTES = [
    ("POST",   r"/api/register",                         register,             False),
    ("POST",   r"/api/login",                            login,                False),
    ("POST",   r"/api/logout",                           logout,               False),
    ("GET",    r"/api/me",                               me,                   True),
    ("PATCH",  r"/api/me/preferences",                   update_preferences,   True),
    ("GET",    r"/api/me/permissions",                   list_permissions,     True),
    ("GET",    r"/api/people/([A-Za-z0-9_.]+)",          person_profile,       True),
    ("GET",    r"/api/people/([A-Za-z0-9_.]+)/devotions", person_devotion_month, True),
    ("GET",    r"/api/people/([A-Za-z0-9_.]+)/devotions/([\d-]+)", person_devotion, True),
    ("GET",    r"/api/people/([A-Za-z0-9_.]+)/prayers",  person_prayers,       True),
    ("GET",    r"/api/users/search",                     search_users,         True),

    ("GET",    r"/api/conversations",                    list_conversations,   True),
    ("POST",   r"/api/conversations",                    create_conversation,  True),
    ("GET",    r"/api/conversations/(\d+)",              get_conversation,     True),
    ("PATCH",  r"/api/conversations/(\d+)/settings",     update_settings,      True),
    ("POST",   r"/api/conversations/(\d+)/members",      add_members,          True),
    ("DELETE", r"/api/conversations/(\d+)/members/(\d+)", remove_member,       True),
    ("POST",   r"/api/conversations/(\d+)/leave",        leave_conversation,   True),
    ("GET",    r"/api/conversations/(\d+)/messages",     list_messages,        True),
    ("POST",   r"/api/conversations/(\d+)/messages",     send_message,         True),
    ("DELETE", r"/api/messages/(\d+)",                   delete_message,       True),

    ("GET",    r"/api/devotions",                        devotions_for_month,  True),
    ("GET",    r"/api/devotions/visible-to",             visible_to,           True),
    ("GET",    r"/api/devotions/([\d-]+)",               get_devotion,         True),
    ("PUT",    r"/api/devotions/([\d-]+)",               save_devotion,        True),
    ("DELETE", r"/api/devotions/([\d-]+)",               delete_devotion,      True),

    ("GET",    r"/api/prayers",                          list_prayers,         True),
    ("POST",   r"/api/prayers",                          add_prayer,           True),
    ("GET",    r"/api/prayers/shared",                   shared_prayer_lists,  True),
    ("PATCH",  r"/api/prayers/(\d+)",                    update_prayer,        True),
    ("DELETE", r"/api/prayers/(\d+)",                    delete_prayer,        True),
]
ROUTES = [(m, re.compile(p + "$"), h, a) for m, p, h, a in ROUTES]
