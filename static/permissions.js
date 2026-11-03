let chats = [];

function renderSummary() {
  const names = (key) => chats.filter((c) => c[key]).map((c) => c.title);
  const line = (label, list) => el("div", {}, el("strong", {}, label + ": "),
    list.length ? list.join(", ") : el("span", { class: "muted" }, "only you"));
  document.getElementById("summary").replaceChildren(
    el("h2", {}, "Who can see what"),
    line("Devotions", names("share_devotions")),
    line("Prayer list", names("share_prayers")));
}

function renderRows() {
  document.getElementById("empty").hidden = chats.length > 0;
  document.getElementById("perm-rows").replaceChildren(...chats.map((c) => {
    const toggle = (key, label) => switchEl(c[key], async (on) => {
      const updated = await api("PATCH", `/api/conversations/${c.id}/settings`, { [key]: on, today: localISO() });
      c[key] = updated[key];
      renderSummary();
    }, `${label} for ${c.title}`);
    return el("tr", {},
      el("th", { scope: "row" },
        el("a", { href: `/chat?c=${c.id}` }, c.title),
        el("div", { class: "muted small" }, c.is_group ? "Group" : "1-on-1")),
      el("td", {}, toggle("share_devotions", "Share devotions")),
      el("td", {}, toggle("share_prayers", "Share prayers")));
  }));
}

(async () => {
  await initPage();
  chats = await api("GET", "/api/me/permissions");
  renderSummary();
  renderRows();
})();
