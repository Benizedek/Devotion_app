"""Low-level chat helpers (membership checks, member lists, titles, posting messages).

Kept apart from the request handlers so chats, messages and sharing can all use them
without importing each other."""
from .validation import ApiError


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
