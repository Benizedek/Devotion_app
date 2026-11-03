from tests.helpers import PASSWORD, ServerTestCase


class AccountTests(ServerTestCase):
    def test_register_login_logout(self):
        c = self.user("ruth")
        self.assertEqual(c.get("/api/me")[1]["username"], "ruth")
        self.assertEqual(c.call("POST", "/api/logout")[0], 200)
        self.assertEqual(c.get("/api/me")[0], 401)
        self.assertEqual(c.call("POST", "/api/login", {"username": "ruth", "password": PASSWORD})[0], 200)

    def test_bad_signups_and_logins(self):
        self.user("naomi")
        anon = self.client()
        self.assertEqual(anon.call("POST", "/api/register", {"username": "NAOMI", "display_name": "x", "password": PASSWORD})[0], 409)
        self.assertEqual(anon.call("POST", "/api/register", {"username": "zz", "display_name": "x", "password": PASSWORD})[0], 400)
        self.assertEqual(anon.call("POST", "/api/register", {"username": "boaz", "display_name": "x", "password": "short"})[0], 400)
        self.assertEqual(anon.call("POST", "/api/login", {"username": "naomi", "password": "wrong-password"})[0], 401)
        self.assertEqual(anon.call("POST", "/api/login", {"username": "nobody", "password": PASSWORD})[0], 401)

    def test_preferences(self):
        c = self.user("esther")
        me = c.ok("GET", "/api/me")
        self.assertEqual((me["theme"], me["full_width"]), ("warm", False))
        self.assertEqual(c.ok("PATCH", "/api/me/preferences", {"theme": "ocean", "full_width": True})["theme"], "ocean")
        self.assertEqual(c.call("PATCH", "/api/me/preferences", {"theme": "neon"})[0], 400)
        self.assertEqual(c.call("PATCH", "/api/me/preferences", {"full_width": "yes"})[0], 400)

    def test_search(self):
        a = self.user("mary", "Mary Magdalene")
        self.user("martha", "Martha B")
        self.assertEqual([u["username"] for u in a.ok("GET", "/api/users/search?q=Mart")], ["martha"])
        self.assertEqual(a.ok("GET", "/api/users/search?q=mary"), [])          # never yourself
        self.assertEqual(a.ok("GET", "/api/users/search?q=m"), [])             # too short
        self.assertEqual(a.ok("GET", "/api/users/search?q=%25%25"), [])        # % is literal, not a wildcard
