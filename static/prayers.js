const $ = (id) => document.getElementById(id);
const REFRESH_MS = 30_000;   // how often others' lists are re-fetched
let sharedLists = [];        // [{owner, username, via: [chat ids], prayers}]
let groups = [];             // group chats, for the filter dropdown

// ---------- my active prayers (answered ones move to /prayers/answered) ----------
function renderMine(all) {
  const active = all.filter((p) => !p.answered_at);
  const answered = all.length - active.length;
  $("answered-link").textContent = `Answered (${answered}) →`;

  const list = $("my-prayers");
  if (!active.length) {
    list.replaceChildren(el("li", { class: "muted" },
      answered ? "Nothing on your list right now. Praise God for the answered ones!" : "No prayers yet. Add your first request above."));
    return;
  }
  list.replaceChildren(...active.map((p) => {
    const li = el("li");
    const view = () => li.replaceChildren(el("div", { class: "stack-tight" },
      el("span", { class: "prayer-title" }, p.title),
      p.body ? el("div", { class: "muted" }, p.body) : null,
      el("div", { class: "row" },
        el("button", { onclick: async () => {
          renderMine(await api("PATCH", `/api/prayers/${p.id}`, { answered: true, today: localISO() }));
          toast("Moved to Answered");
        } }, "Mark answered"),
        el("button", { onclick: edit }, "Edit"),
        el("button", { class: "danger", onclick: async () => {
          if (confirm("Remove this prayer from your list?")) renderMine(await api("DELETE", `/api/prayers/${p.id}`));
        } }, "Remove"))));
    const edit = () => {
      const t = el("input", { value: p.title, maxlength: 200, "aria-label": "Prayer request" });
      const b = el("input", { value: p.body, maxlength: 5000, placeholder: "Details", "aria-label": "Details" });
      const err = el("div", { class: "error" });
      li.replaceChildren(el("div", { class: "stack" }, t, b, err, el("div", { class: "row" },
        el("button", { class: "primary", onclick: async () => {
          try { renderMine(await api("PATCH", `/api/prayers/${p.id}`, { title: t.value, body: b.value })); }
          catch (e) { err.textContent = e.message; }
        } }, "Save"),
        el("button", { onclick: view }, "Cancel"))));
      t.focus();
    };
    view();
    return li;
  }));
}

$("add-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("add-error").textContent = "";
  try {
    renderMine(await api("POST", "/api/prayers", { title: $("new-title").value, body: $("new-body").value }));
    $("new-title").value = ""; $("new-body").value = "";
  } catch (err) { $("add-error").textContent = err.message; }
});

// ---------- others' lists, with a group / person filter ----------
// Filter values: "all", "group:<chat id>", "person:<username>"
function renderFilter() {
  const select = $("filter");
  const current = select.value || "all";
  const people = sharedLists.map((l) => [l.username, l.owner]);
  const sharedGroups = groups.filter((g) => sharedLists.some((l) => l.via.includes(g.id)));
  select.replaceChildren(
    el("option", { value: "all" }, "Everyone"),
    sharedGroups.length ? el("optgroup", { label: "Groups" },
      sharedGroups.map((g) => el("option", { value: `group:${g.id}` }, g.title))) : null,
    people.length ? el("optgroup", { label: "People" },
      people.map(([u, name]) => el("option", { value: `person:${u}` }, name))) : null);
  // Keep the choice across refreshes if it still exists.
  select.value = [...select.options].some((o) => o.value === current) ? current : "all";
}

function renderShared() {
  const [kind, value] = $("filter").value.split(":");
  const shown = sharedLists.filter((l) =>
    kind === "group" ? l.via.includes(Number(value)) : kind === "person" ? l.username === value : true);

  if (!sharedLists.length) {
    $("shared-lists").replaceChildren(el("p", { class: "muted" },
      "No one is sharing a prayer list with you yet. When someone in one of your chats turns on prayer sharing, their list shows up here."));
    return;
  }
  $("shared-lists").replaceChildren(...shown.map((l) => el("div", {},
    el("h3", {}, el("a", { href: `/person?u=${encodeURIComponent(l.username)}`, class: "person-link" }, l.owner),
      " ", el("span", { class: "muted" }, `@${l.username}`)),
    l.prayers.length
      ? el("ul", { class: "list" }, l.prayers.map((p) => el("li", {},
          el("span", { class: "prayer-title" }, p.title),
          p.body ? el("div", { class: "muted" }, p.body) : null)))
      : el("p", { class: "muted" }, "No requests right now."))));
}

async function loadShared() {
  sharedLists = await api("GET", "/api/prayers/shared");
  $("refreshed").textContent = `Updated ${new Date().toLocaleTimeString()} · refreshes automatically`;
  renderFilter();
  renderShared();
}

$("filter").addEventListener("change", renderShared);

(async () => {
  await initPage();
  const [mine, convs] = await Promise.all([api("GET", "/api/prayers"), api("GET", "/api/conversations")]);
  renderMine(mine);
  groups = convs.filter((c) => c.is_group);
  await loadShared();
  setInterval(() => { if (!document.hidden) loadShared(); }, REFRESH_MS);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) loadShared(); });
})();
