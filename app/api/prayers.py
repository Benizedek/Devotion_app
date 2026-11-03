"""Your prayer list (active + answered archive) and the lists others share with you."""
from datetime import date

from .validation import ApiError, parse_date, parse_id, text


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


# (method, path pattern, handler, login required)
ROUTES = [
    ("GET",    r"/api/prayers", list_prayers, True),
    ("POST",   r"/api/prayers", add_prayer, True),
    ("GET",    r"/api/prayers/shared", shared_prayer_lists, True),
    ("PATCH",  r"/api/prayers/(\d+)", update_prayer, True),
    ("DELETE", r"/api/prayers/(\d+)", delete_prayer, True),
]
