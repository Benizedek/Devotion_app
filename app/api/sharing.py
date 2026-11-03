"""Who can see what: the per-chat devotion and prayer switches, and the Permissions page."""
from .chat_store import members_of, post_message, require_member, title_for
from .chats import get_conversation
from .validation import ApiError, parse_date, parse_id


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


def sharing_chats(conn, user) -> list[dict]:
    """Chats I've turned devotion sharing on for."""
    rows = conn.execute(
        """SELECT c.id, c.name, c.is_group FROM conversations c
           JOIN conversation_members m ON m.conversation_id = c.id
           WHERE m.user_id = ? AND m.share_devotions = 1""",
        (user["id"],),
    ).fetchall()
    return [{"id": r["id"], "title": title_for(r, members_of(conn, r["id"]), user["id"])} for r in rows]


def post_devotion_if_new(conn, user, conv_id: int, entry_date: str):
    row = conn.execute("SELECT id FROM devotions WHERE user_id = ? AND entry_date = ?",
                       (user["id"], entry_date)).fetchone()
    if row is None:
        return
    already = conn.execute("SELECT 1 FROM messages WHERE conversation_id = ? AND devotion_id = ?",
                           (conv_id, row["id"])).fetchone()
    if not already:
        post_message(conn, conv_id, user["id"], "devotion", devotion_id=row["id"])


# (method, path pattern, handler, login required)
ROUTES = [
    ("PATCH",  r"/api/conversations/(\d+)/settings", update_settings, True),
    ("GET",    r"/api/me/permissions", list_permissions, True),
]
