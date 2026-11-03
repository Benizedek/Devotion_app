from tests.helpers import ServerTestCase


class ChatTests(ServerTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ben, cls.grace, cls.joe, cls.mal = (cls.user(u) for u in ("ben", "grace", "joe", "mal"))

    def test_direct_chat_is_reused(self):
        a = self.ben.ok("POST", "/api/conversations", {"user_ids": [self.grace.id]})["id"]
        b = self.grace.ok("POST", "/api/conversations", {"user_ids": [self.ben.id]})["id"]
        self.assertEqual(a, b)

    def test_messages_and_unread(self):
        dm = self.ben.ok("POST", "/api/conversations", {"user_ids": [self.joe.id]})["id"]
        self.ben.ok("POST", f"/api/conversations/{dm}/messages", {"body": "Praying for you!"})
        unread = {c["id"]: c["unread"] for c in self.joe.ok("GET", "/api/conversations")}
        self.assertEqual(unread[dm], 1)
        self.assertEqual([m["body"] for m in self.joe.ok("GET", f"/api/conversations/{dm}/messages")], ["Praying for you!"])
        unread = {c["id"]: c["unread"] for c in self.joe.ok("GET", "/api/conversations")}
        self.assertEqual(unread[dm], 0)                          # reading clears it

    def test_outsiders_are_locked_out(self):
        dm = self.ben.ok("POST", "/api/conversations", {"user_ids": [self.grace.id]})["id"]
        self.assertEqual(self.mal.get(f"/api/conversations/{dm}/messages")[0], 404)
        self.assertEqual(self.mal.call("POST", f"/api/conversations/{dm}/messages", {"body": "hi"})[0], 404)

    def test_unsend_only_your_own(self):
        dm = self.ben.ok("POST", "/api/conversations", {"user_ids": [self.grace.id]})["id"]
        mid = self.ben.ok("POST", f"/api/conversations/{dm}/messages", {"body": "oops"})["id"]
        self.grace.call("DELETE", f"/api/messages/{mid}")
        self.assertIn(mid, [m["id"] for m in self.ben.ok("GET", f"/api/conversations/{dm}/messages")])
        self.ben.ok("DELETE", f"/api/messages/{mid}")
        self.assertNotIn(mid, [m["id"] for m in self.ben.ok("GET", f"/api/conversations/{dm}/messages")])

    def test_group_members_add_remove_leave(self):
        g = self.ben.ok("POST", "/api/conversations", {"user_ids": [self.grace.id, self.joe.id], "name": "Study"})["id"]
        self.assertEqual(self.joe.ok("GET", f"/api/conversations/{g}")["title"], "Study")
        self.assertEqual(len(self.ben.ok("POST", f"/api/conversations/{g}/members", {"user_ids": [self.mal.id]})["members"]), 4)
        # only the creator removes people
        self.assertEqual(self.grace.call("DELETE", f"/api/conversations/{g}/members/{self.joe.id}")[0], 403)
        self.assertEqual(self.ben.call("DELETE", f"/api/conversations/{g}/members/{self.ben.id}")[0], 400)
        self.ben.ok("DELETE", f"/api/conversations/{g}/members/{self.joe.id}")
        self.assertEqual(self.joe.get(f"/api/conversations/{g}/messages")[0], 404)
        # creator leaves -> longest-standing member takes over
        self.ben.ok("POST", f"/api/conversations/{g}/leave")
        self.assertTrue(self.grace.ok("GET", f"/api/conversations/{g}")["is_admin"])

    def test_direct_chat_rules(self):
        dm = self.ben.ok("POST", "/api/conversations", {"user_ids": [self.mal.id]})["id"]
        self.assertEqual(self.ben.call("POST", f"/api/conversations/{dm}/members", {"user_ids": [self.joe.id]})[0], 400)
        self.assertEqual(self.ben.call("POST", f"/api/conversations/{dm}/leave")[0], 400)

    def test_bad_member_lists(self):
        self.assertEqual(self.ben.call("POST", "/api/conversations", {"user_ids": ["x"]})[0], 400)
        self.assertEqual(self.ben.call("POST", "/api/conversations", {"user_ids": [99999]})[0], 404)
        self.assertEqual(self.ben.call("POST", "/api/conversations", {"user_ids": [self.ben.id]})[0], 400)
