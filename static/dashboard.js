const $ = (id) => document.getElementById(id);

(async () => {
  const me = await initPage();
  const today = localISO();
  const isNew = new URLSearchParams(location.search).get("new") === "1";

  $("welcome").textContent = isNew ? `Welcome to Daily Bread, ${me.display_name}!` : `Welcome back, ${me.display_name}`;
  $("welcome-sub").textContent = isNew
    ? "Your account is ready. Start with today's devotion or add a prayer request."
    : prettyDate(today);

  const [stats, devotion, prayers, sharedDevotions, sharedLists] = await Promise.all([
    api("GET", `/api/devotions/stats?today=${today}`),
    api("GET", `/api/devotions/${today}`),
    api("GET", "/api/prayers"),
    api("GET", "/api/devotions/shared"),
    api("GET", "/api/prayers/shared"),
  ]);

  $("stats").replaceChildren(
    ...[[stats.current_streak, "day streak"], [stats.longest_streak, "longest streak"],
        [`${stats.last_30_days}/30`, "last 30 days"], [stats.total, "total devotions"]]
      .map(([n, label]) => el("div", { class: "stat" }, el("b", {}, n), el("span", {}, label))));

  // Today's devotion
  $("today-card").replaceChildren(
    el("h2", {}, "Today's devotion"),
    devotion
      ? el("div", { class: "stack" },
          el("div", {}, el("span", { class: "badge" }, "Done"), " ", devotion.title || "Untitled"),
          devotion.scripture ? el("div", { class: "muted" }, devotion.scripture) : null,
          el("a", { href: "/calendar" }, "View or edit"))
      : el("div", { class: "stack" },
          el("p", { class: "muted" }, "You haven't written today's devotion yet."),
          el("a", { href: "/calendar" }, "Write today's devotion")));

  // Prayer list summary
  const active = prayers.filter((p) => !p.answered_at);
  const answered = prayers.length - active.length;
  $("prayer-card").replaceChildren(
    el("h2", {}, "My prayer list"),
    prayers.length
      ? el("div", { class: "stack" },
          el("div", {}, `${active.length} still praying · ${answered} answered`),
          active.slice(0, 3).map((p) => el("div", { class: "muted" }, "• " + p.title)),
          el("a", { href: "/prayers" }, "Open prayer list"))
      : el("div", { class: "stack" },
          el("p", { class: "muted" }, "No prayer requests yet."),
          el("a", { href: "/prayers" }, "Add your first prayer")));

  // Shared with me
  const othersPrayers = sharedLists.reduce((n, l) => n + l.prayers.filter((p) => !p.answered_at).length, 0);
  $("shared-card").replaceChildren(
    el("h2", {}, "Shared with me"),
    el("p", { class: "muted" },
      `${sharedDevotions.length} shared devotion${sharedDevotions.length === 1 ? "" : "s"} · ` +
      `${othersPrayers} open prayer request${othersPrayers === 1 ? "" : "s"} from ${sharedLists.length} ` +
      `${sharedLists.length === 1 ? "person" : "people"}`),
    sharedDevotions.length
      ? el("ul", { class: "list" }, sharedDevotions.slice(0, 3).map((d) => el("li", {},
          el("strong", {}, d.title || "Devotion"),
          el("div", { class: "muted" }, `${d.author} · ${prettyDate(d.entry_date)}`))))
      : el("p", { class: "muted" }, "When someone shares a devotion with you or your group, it appears here."),
    el("div", { class: "row" },
      el("a", { href: "/shared" }, "All shared devotions"), " · ",
      el("a", { href: "/prayers" }, "Pray for others"), " · ",
      el("a", { href: "/groups" }, "Manage groups")));
})();
