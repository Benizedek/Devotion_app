"""Your own devotions. Only today's can be written or changed; past days are read-only."""
import re
from datetime import date

from .sharing import post_devotion_if_new, sharing_chats
from .validation import ApiError, parse_date, text


DEVOTION_FIELDS = ("observations", "interpretation", "application")


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


# (method, path pattern, handler, login required)
ROUTES = [
    ("GET",    r"/api/devotions", devotions_for_month, True),
    ("GET",    r"/api/devotions/visible-to", visible_to, True),
    ("GET",    r"/api/devotions/([\d-]+)", get_devotion, True),
    ("PUT",    r"/api/devotions/([\d-]+)", save_devotion, True),
    ("DELETE", r"/api/devotions/([\d-]+)", delete_devotion, True),
]
