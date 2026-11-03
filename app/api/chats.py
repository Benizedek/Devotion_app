"""Chats (1-on-1 and groups): listing, creating, members, leaving."""
from .chat_store import members_of, post_message, preview_text, require_member, title_for
from .validation import ApiError, parse_id, text


MAX_GROUP_SIZE = 50


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


# (method, path pattern, handler, login required)
ROUTES = [
    ("GET",    r"/api/conversations", list_conversations, True),
    ("POST",   r"/api/conversations", create_conversation, True),
    ("GET",    r"/api/conversations/(\d+)", get_conversation, True),
    ("POST",   r"/api/conversations/(\d+)/members", add_members, True),
    ("DELETE", r"/api/conversations/(\d+)/members/(\d+)", remove_member, True),
    ("POST",   r"/api/conversations/(\d+)/leave", leave_conversation, True),
]
