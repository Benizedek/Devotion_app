"""Messages inside a chat: reading (which also marks them read), sending, unsending."""
from .chat_store import post_message, require_member
from .devotions import DEVOTION_FIELDS
from .validation import parse_id, text


MAX_MESSAGE = 4_000


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


# (method, path pattern, handler, login required)
ROUTES = [
    ("GET",    r"/api/conversations/(\d+)/messages", list_messages, True),
    ("POST",   r"/api/conversations/(\d+)/messages", send_message, True),
    ("DELETE", r"/api/messages/(\d+)", delete_message, True),
]
