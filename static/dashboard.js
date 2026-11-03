const $ = (id) => document.getElementById(id);

(async () => {
  const me = await initPage();
  const today = localISO();
  const isNew = new URLSearchParams(location.search).get("new") === "1";

  $("welcome").textContent = isNew ? `Welcome to Daily Bread, ${me.display_name}!` : `Welcome back, ${me.display_name}`;
  $("welcome-sub").textContent = isNew
    ? "Your account is ready. Start with today's devotion or add a prayer request."
    : prettyDate(today);

  const [devotion, prayers, convs] = await Promise.all([
    api("GET", `/api/devotions/${today}`),
    api("GET", "/api/prayers"),
    api("GET", "/api/conversations"),
  ]);

  // Today's devotion
  $("today-card").replaceChildren(
    el("h2", {}, "Today's devotion"),
    devotion
      ? el("div", { class: "stack" },
          el("div", {}, el("span", { class: "badge" }, "Done"), " ", devotion.scripture || "Written today"),
          el("a", { href: "/calendar" }, "View or edit"))
      : el("div", { class: "stack" },
          el("p", { class: "muted" }, "You haven't written today's devotion yet."),
          el("a", { href: "/calendar" }, "Write today's devotion")));

  // Prayer list summary
  const active = prayers.filter((p) => !p.answered_at);
  $("prayer-card").replaceChildren(
    el("h2", {}, "My prayer list"),
    prayers.length
      ? el("div", { class: "stack" },
          el("div", {}, `${active.length} still praying · ${prayers.length - active.length} answered`),
          active.slice(0, 3).map((p) => el("div", { class: "muted" }, "• " + p.title)),
          el("a", { href: "/prayers" }, "Open prayer list"))
      : el("div", { class: "stack" },
          el("p", { class: "muted" }, "No prayer requests yet."),
          el("a", { href: "/prayers" }, "Add your first prayer")));

  // Recent chats
  $("chats-card").replaceChildren(
    el("div", { class: "row spread" }, el("h2", {}, "Recent chats"), el("a", { href: "/groups" }, "+ New chat")),
    convs.length
      ? el("ul", { class: "list" }, convs.slice(0, 5).map((c) => el("li", {},
          el("a", { class: "conv-link", href: `/shared?c=${c.id}` },
            el("div", { class: "conv-top" },
              el("strong", {}, c.title),
              c.unread ? el("span", { class: "nav-badge" }, c.unread) : el("span", { class: "muted small" }, shortTime(c.last_at))),
            el("div", { class: `conv-preview${c.unread ? " unread" : ""}` }, c.preview || "No messages yet")))))
      : el("p", { class: "muted" }, "No chats yet. Start one with a friend or your small group to share devotions and prayers."));
})();
