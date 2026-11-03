import urllib.error
import urllib.request

from tests.helpers import ServerTestCase


class SecurityTests(ServerTestCase):
    def raw_status(self, path):
        """GET a path exactly as written (no ../ cleanup), the way an attacker would send it."""
        import http.client
        host, port = self.base.removeprefix("http://").split(":")
        conn = http.client.HTTPConnection(host, int(port))
        conn.request("GET", path)
        status = conn.getresponse().status
        conn.close()
        return status

    def test_login_required(self):
        anon = self.client()
        for path in ("/api/me", "/api/prayers", "/api/conversations", f"/api/devotions/{self.today}"):
            self.assertEqual(anon.get(path)[0], 401, path)

    def test_writes_must_be_json(self):
        # A cross-site HTML form can't send application/json, so this blocks CSRF.
        c = self.user("watchman")
        self.assertEqual(c.call("POST", "/api/prayers", {"title": "x"}, content_type="text/plain")[0], 415)

    def test_cannot_read_files_outside_frontend(self):
        for path in ("/static/../app/config.py", "/static/%2e%2e/app/auth.py", "/static/pages/../../server.py"):
            self.assertEqual(self.raw_status(path), 404, path)

    def test_pages_and_assets_are_served(self):
        for path in ("/", "/dashboard", "/chat", "/static/css/app.css", "/static/js/lib/api.js"):
            with urllib.request.urlopen(self.base + path) as res:
                self.assertEqual(res.status, 200, path)
                self.assertIn("default-src 'self'", res.headers["Content-Security-Policy"])
