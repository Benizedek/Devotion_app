from tests.helpers import ServerTestCase


class PrayerTests(ServerTestCase):
    def test_add_answer_unanswer(self):
        c = self.user("hannah")
        pid = c.ok("POST", "/api/prayers", {"title": "A child"})[0]["id"]
        answered = c.ok("PATCH", f"/api/prayers/{pid}", {"answered": True, "today": self.today})
        self.assertEqual(answered[0]["answered_at"], self.today)
        self.assertIsNone(c.ok("PATCH", f"/api/prayers/{pid}", {"answered": False})[0]["answered_at"])

    def test_cannot_touch_someone_elses(self):
        a, b = self.user("eli"), self.user("samuel")
        pid = a.ok("POST", "/api/prayers", {"title": "Mine"})[0]["id"]
        self.assertEqual(b.call("PATCH", f"/api/prayers/{pid}", {"title": "hacked"})[0], 404)
        b.call("DELETE", f"/api/prayers/{pid}")
        self.assertEqual(len(a.ok("GET", "/api/prayers")), 1)
