"""Test helpers: run the real server on a throwaway database, and a small client that keeps cookies.

Each test class gets its own empty database in a temporary folder, so tests never touch data/.
"""
import http.cookiejar
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

from app import config, server

PASSWORD = "longenough1"


class Client:
    """One logged-in browser: remembers its session cookie between requests."""

    def __init__(self, base_url):
        self.base = base_url
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def call(self, method, path, body=None, content_type="application/json"):
        """Returns (status code, parsed JSON)."""
        data = json.dumps(body or {}).encode() if method != "GET" else None
        headers = {"Content-Type": content_type} if method != "GET" else {}
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=headers)
        try:
            with self.opener.open(req) as res:
                return res.status, json.loads(res.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def get(self, path):
        return self.call("GET", path)

    def ok(self, method, path, body=None):
        """Like call(), but fails the test unless the server answers 200. Returns just the JSON."""
        status, data = self.call(method, path, body)
        assert status == 200, f"{method} {path} -> {status} {data}"
        return data


class ServerTestCase(unittest.TestCase):
    """Starts the app once per test class on a random free port with a fresh database."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        config.DB_PATH = Path(cls._tmp.name) / "test.db"
        server.Handler.log_message = lambda *args: None      # keep test output readable
        cls.server = server.make_server("127.0.0.1", 0)       # port 0 = any free port
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.today = str(date.today())

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls._tmp.cleanup()

    @classmethod
    def client(cls):
        return Client(cls.base)

    @classmethod
    def user(cls, username, display_name=None):
        """A new account, already logged in. Works in setUpClass too."""
        c = cls.client()
        c.ok("POST", "/api/register", {"username": username, "display_name": display_name or username.title(),
                                       "password": PASSWORD})
        c.id = c.ok("GET", "/api/me")["id"]
        c.username = username
        return c
