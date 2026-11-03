"""HTTP plumbing, standard library only: routing, JSON in/out, cookies, static files, headers.

No business rules live here; they're in app/api/. Start it with `python server.py` in the project folder.
In production, put Nginx in front and set SECURE_COOKIES=1 so cookies require HTTPS.
"""
import json
import traceback
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import auth, config, db, router
from .api.validation import ApiError

STATIC_DIR = config.FRONTEND_DIR.resolve()
PAGES_DIR = STATIC_DIR / "pages"

# URL path -> HTML file in frontend/pages/. Each page loads its script from frontend/js/pages/.
PAGES = {
    "/":                 "login.html",
    "/dashboard":        "dashboard.html",
    "/calendar":         "devotions.html",
    "/prayers":          "prayers.html",
    "/prayers/answered": "prayers-answered.html",
    "/chat":             "chat.html",
    "/chat/new":         "new-chat.html",
    "/person":           "person.html",
    "/settings":         "settings.html",
    "/permissions":      "permissions.html",
    # Older URLs, kept so bookmarks and old links still work
    "/shared":           "chat.html",
    "/groups":           "new-chat.html",
}
CONTENT_TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
                 ".js": "text/javascript; charset=utf-8", ".svg": "image/svg+xml", ".ico": "image/x-icon"}
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "same-origin",
    "Content-Security-Policy": "default-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
}


class Handler(BaseHTTPRequestHandler):
    server_version = "Devotion/0.1"

    # Every method goes through the same dispatcher.
    def do_GET(self): self.dispatch()
    def do_POST(self): self.dispatch()
    def do_PUT(self): self.dispatch()
    def do_PATCH(self): self.dispatch()
    def do_DELETE(self): self.dispatch()

    def dispatch(self):
        url = urlparse(self.path)
        if url.path.startswith("/api/"):
            self.handle_api(url)
        elif self.command == "GET":
            self.serve_static(url.path)
        else:
            self.send_json(405, {"error": "Method not allowed"})

    # ---------- API ----------
    def handle_api(self, url):
        route = router.find(self.command, url.path)
        if route is None:
            return self.send_json(404, {"error": "Not found"})
        handler, needs_login, args = route

        # Writes must be JSON. A cross-site HTML form can't send this content type,
        # which (with SameSite=Lax cookies) blocks CSRF.
        body = {}
        if self.command != "GET":
            if not self.headers.get("Content-Type", "").startswith("application/json"):
                return self.send_json(415, {"error": "Send JSON"})
            length = int(self.headers.get("Content-Length") or 0)
            if length > config.MAX_BODY:
                return self.send_json(413, {"error": "Request too large"})
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError:
                return self.send_json(400, {"error": "Invalid JSON"})
            if not isinstance(body, dict):
                return self.send_json(400, {"error": "Expected a JSON object"})

        query = {k: v[0] for k, v in parse_qs(url.query).items()}
        token = self.session_token()
        conn = db.connect()
        try:
            with conn:  # commits on success, rolls back on exception
                user = auth.user_for_token(conn, token)
                if needs_login and user is None:
                    return self.send_json(401, {"error": "Please log in"})
                result = handler(conn, user, args, body, query)
                cookie = None
                if isinstance(result, dict) and "_set_session" in result:
                    cookie = auth.session_cookie(result.pop("_set_session"), config.SECURE_COOKIES)
                elif isinstance(result, dict) and result.pop("_clear_session", False):
                    auth.delete_session(conn, token)
                    cookie = auth.clear_cookie(config.SECURE_COOKIES)
            self.send_json(200, result, cookie)
        except ApiError as e:
            self.send_json(e.status, {"error": e.message})
        except Exception:
            self.log_error("Unhandled error on %s %s", self.command, url.path)
            traceback.print_exc()
            self.send_json(500, {"error": "Something went wrong"})
        finally:
            conn.close()

    def session_token(self):
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        return cookie[auth.COOKIE_NAME].value if auth.COOKIE_NAME in cookie else None

    def send_json(self, status, payload, cookie=None):
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        for k, v in SECURITY_HEADERS.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    # ---------- static files ----------
    def serve_static(self, path):
        if path in PAGES:
            file = PAGES_DIR / PAGES[path]
        elif path.startswith("/static/"):
            file = (STATIC_DIR / path.removeprefix("/static/")).resolve()
            if not file.is_relative_to(STATIC_DIR):   # block ../ path traversal
                return self.send_json(404, {"error": "Not found"})
        else:
            return self.send_json(404, {"error": "Not found"})
        if not file.is_file():
            return self.send_json(404, {"error": "Not found"})
        data = file.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", CONTENT_TYPES.get(file.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        for k, v in SECURITY_HEADERS.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)


def make_server(host=None, port=None):
    """Create the database if needed and return a server that isn't running yet (used by tests too)."""
    db.init()
    return ThreadingHTTPServer((host or config.HOST, config.PORT if port is None else port), Handler)


def main():
    server = make_server()
    print(f"Serving on http://{config.HOST}:{config.PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
