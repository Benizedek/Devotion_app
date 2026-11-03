(async () => {
  await initPage();
  const items = await api("GET", "/api/devotions/shared");
  const feed = document.getElementById("feed");
  if (!items.length) {
    feed.replaceChildren(el("p", { class: "muted" },
      "Nothing shared with you yet. When someone shares a devotion with you or one of your groups, it appears here."));
    return;
  }
  feed.replaceChildren(...items.map((d) => el("article", { class: "card stack" },
    el("div", {},
      el("h2", {}, d.title || "Devotion"),
      el("div", { class: "muted" }, `${d.author} · ${prettyDate(d.entry_date)} · shared with ${d.via}`)),
    d.scripture ? el("div", {}, el("strong", {}, d.scripture)) : null,
    el("div", { class: "devotion-text" }, d.body))));
})();
