"""The two per-chat switches (devotions, prayers) and what other people can see because of them."""
from tests.helpers import ServerTestCase

ENTRY = {"scripture": "Romans 8:28", "observations": "All things work together", "interpretation": "", "application": ""}


class SharingTests(ServerTestCase):
    def setUp(self):
        # Fresh people for every test, so tests don't affect each other's switches.
        n = self._testMethodName[-12:]
        self.ben, self.grace, self.mal = self.user(f"b{n}"), self.user(f"g{n}"), self.user(f"m{n}")
        self.dm = self.ben.ok("POST", "/api/conversations", {"user_ids": [self.grace.id]})["id"]

    def share(self, client, chat, **flags):
        return client.ok("PATCH", f"/api/conversations/{chat}/settings", {**flags, "today": self.today})

    def devotion_statuses(self, viewer, chat):
        return [m["devotion_status"] for m in viewer.ok("GET", f"/api/conversations/{chat}/messages") if m["kind"] == "devotion"]

    def test_off_by_default(self):
        c = self.ben.ok("GET", f"/api/conversations/{self.dm}")
        self.assertEqual((c["share_devotions"], c["share_prayers"]), (False, False))

    def test_devotion_posts_only_where_shared(self):
        self.share(self.ben, self.dm, share_devotions=True)
        other = self.ben.ok("POST", "/api/conversations", {"user_ids": [self.mal.id]})["id"]
        self.ben.ok("PUT", f"/api/devotions/{self.today}", {**ENTRY, "today": self.today})
        self.ben.ok("PUT", f"/api/devotions/{self.today}", {**ENTRY, "application": "edited", "today": self.today})
        self.assertEqual(self.devotion_statuses(self.grace, self.dm), ["shown"])      # posted once, edits don't repost
        self.assertEqual(self.devotion_statuses(self.mal, other), [])

    def test_turning_devotions_off_hides_them(self):
        self.share(self.ben, self.dm, share_devotions=True)
        self.ben.ok("PUT", f"/api/devotions/{self.today}", {**ENTRY, "today": self.today})
        self.share(self.ben, self.dm, share_devotions=False)
        msg = [m for m in self.grace.ok("GET", f"/api/conversations/{self.dm}/messages") if m["kind"] == "devotion"][0]
        self.assertEqual((msg["devotion_status"], msg["devotion"]), ("hidden", None))   # content never sent
        self.assertEqual(self.devotion_statuses(self.ben, self.dm), ["shown"])           # author still sees it

    def test_turning_on_posts_todays_devotion(self):
        self.ben.ok("PUT", f"/api/devotions/{self.today}", {**ENTRY, "today": self.today})
        self.share(self.ben, self.dm, share_devotions=True)
        self.assertEqual(self.devotion_statuses(self.grace, self.dm), ["shown"])

    def test_prayers_and_devotions_are_separate(self):
        self.ben.ok("POST", "/api/prayers", {"title": "Safe travels"})
        self.share(self.ben, self.dm, share_prayers=True)
        self.assertEqual([l["username"] for l in self.grace.ok("GET", "/api/prayers/shared")], [self.ben.username])
        profile = self.grace.ok("GET", f"/api/people/{self.ben.username}")
        self.assertEqual((profile["can_see_devotions"], profile["can_see_prayers"]), (False, True))
        self.assertEqual(self.grace.get(f"/api/people/{self.ben.username}/devotions?month={self.today[:7]}")[0], 403)

    def test_answered_prayers_stay_private(self):
        pid = self.ben.ok("POST", "/api/prayers", {"title": "New job"})[0]["id"]
        self.share(self.ben, self.dm, share_prayers=True)
        self.ben.ok("PATCH", f"/api/prayers/{pid}", {"answered": True, "today": self.today})
        self.assertEqual(self.grace.ok("GET", f"/api/people/{self.ben.username}/prayers"), [])

    def test_person_page(self):
        self.ben.ok("PUT", f"/api/devotions/{self.today}", {**ENTRY, "today": self.today})
        self.share(self.ben, self.dm, share_devotions=True)
        base = f"/api/people/{self.ben.username}"
        self.assertEqual(self.grace.ok("GET", f"{base}/devotions?month={self.today[:7]}"), [self.today])
        self.assertEqual(self.grace.ok("GET", f"{base}/devotions/{self.today}")["scripture"], "Romans 8:28")
        stranger = self.mal.ok("GET", base)                       # mal shares no chat with ben
        self.assertEqual((stranger["can_see_devotions"], stranger["can_see_prayers"]), (False, False))
        self.assertEqual(self.mal.get(f"{base}/prayers")[0], 403)
        self.assertEqual(self.grace.get("/api/people/nobody")[0], 404)

    def test_filter_data_lists_each_chat(self):
        group = self.ben.ok("POST", "/api/conversations", {"user_ids": [self.grace.id, self.mal.id], "name": "Study"})["id"]
        self.share(self.ben, self.dm, share_prayers=True)
        self.share(self.ben, group, share_prayers=True)
        self.assertEqual(sorted(self.grace.ok("GET", "/api/prayers/shared")[0]["via"]), sorted([self.dm, group]))
        self.assertEqual(self.mal.ok("GET", "/api/prayers/shared")[0]["via"], [group])

    def test_leaving_stops_sharing(self):
        group = self.ben.ok("POST", "/api/conversations", {"user_ids": [self.grace.id, self.mal.id], "name": "G"})["id"]
        self.share(self.mal, group, share_prayers=True)
        self.mal.ok("POST", f"/api/conversations/{group}/leave")
        self.assertEqual(self.grace.ok("GET", "/api/prayers/shared"), [])

    def test_permissions_page_and_bad_input(self):
        self.share(self.ben, self.dm, share_prayers=True)
        perms = self.ben.ok("GET", "/api/me/permissions")
        self.assertEqual([(p["share_devotions"], p["share_prayers"]) for p in perms], [(False, True)])
        self.assertEqual(self.ben.call("PATCH", f"/api/conversations/{self.dm}/settings", {})[0], 400)
        self.assertEqual(self.ben.call("PATCH", f"/api/conversations/{self.dm}/settings", {"share_prayers": 1})[0], 400)
