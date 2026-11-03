"""Another person's page: their devotions and prayers, if they share them with you."""
from .devotions import devotions_for_month, get_devotion
from .prayers import active_prayers
from .validation import ApiError


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


# (method, path pattern, handler, login required)
ROUTES = [
    ("GET",    r"/api/people/([A-Za-z0-9_.]+)", person_profile, True),
    ("GET",    r"/api/people/([A-Za-z0-9_.]+)/devotions", person_devotion_month, True),
    ("GET",    r"/api/people/([A-Za-z0-9_.]+)/devotions/([\d-]+)", person_devotion, True),
    ("GET",    r"/api/people/([A-Za-z0-9_.]+)/prayers", person_prayers, True),
]
