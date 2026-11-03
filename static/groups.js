const $ = (id) => document.getElementById(id);

function render(groups) {
  if (!groups.length) {
    $("groups").replaceChildren(el("p", { class: "muted" }, "You're not in any groups yet. Start one, or join with a code."));
    return;
  }
  $("groups").replaceChildren(...groups.map((g) => el("section", { class: "card stack" },
    el("div", { class: "row" },
      el("h2", {}, g.name),
      g.is_owner ? el("span", { class: "badge" }, "Leader") : null),
    el("div", { class: "row" },
      el("span", { class: "muted" }, "Invite code:"),
      el("code", { class: "invite" }, g.invite_code),
      el("button", { onclick: async () => {
        await navigator.clipboard.writeText(g.invite_code);
        toast("Invite code copied");
      } }, "Copy")),
    el("div", { class: "muted" }, `${g.members.length} member${g.members.length === 1 ? "" : "s"}: `,
      g.members.map((m) => `${m.display_name} (@${m.username})`).join(", ")),
    el("div", {}, el("button", { class: "danger", onclick: async () => {
      if (confirm(`Leave ${g.name}? Things shared with this group will no longer be visible to you.`))
        render(await api("POST", `/api/groups/${g.id}/leave`));
    } }, "Leave group")))));
}

$("create-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("create-error").textContent = "";
  try { render(await api("POST", "/api/groups", { name: $("group-name").value })); $("group-name").value = ""; }
  catch (err) { $("create-error").textContent = err.message; }
});

$("join-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("join-error").textContent = "";
  try { render(await api("POST", "/api/groups/join", { code: $("join-code").value })); $("join-code").value = ""; toast("Joined"); }
  catch (err) { $("join-error").textContent = err.message; }
});

(async () => {
  await initPage();
  render(await api("GET", "/api/groups"));
})();
