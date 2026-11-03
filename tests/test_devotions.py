from datetime import date, timedelta

from tests.helpers import ServerTestCase

ENTRY = {"scripture": "John 15:1-5", "observations": "I am the vine", "interpretation": "Abide in Him",
         "application": "Pray before my phone"}


class DevotionTests(ServerTestCase):
    def test_write_today_and_read_back(self):
        c = self.user("timothy")
        saved = c.ok("PUT", f"/api/devotions/{self.today}", {**ENTRY, "today": self.today})
        self.assertEqual(saved["observations"], "I am the vine")
        self.assertEqual(c.ok("GET", f"/api/devotions?month={self.today[:7]}"), [self.today])

    def test_only_today_is_editable(self):
        c = self.user("titus")
        past = str(date.today() - timedelta(days=3))
        self.assertEqual(c.call("PUT", f"/api/devotions/{self.today}", ENTRY)[0], 400)                  # no 'today'
        self.assertEqual(c.call("PUT", f"/api/devotions/{past}", {**ENTRY, "today": past})[0], 403)    # far past
        self.assertEqual(c.call("PUT", f"/api/devotions/{past}", {**ENTRY, "today": self.today})[0], 403)  # mismatch
        self.assertEqual(c.call("DELETE", f"/api/devotions/{past}", {"today": past})[0], 403)

    def test_needs_some_content(self):
        c = self.user("silas")
        self.assertEqual(c.call("PUT", f"/api/devotions/{self.today}", {"scripture": "Ps 23", "today": self.today})[0], 400)
