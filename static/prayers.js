const $ = (id) => document.getElementById(id);
const REFRESH_MS = 30_000;   // how often shared lists are re-fetched

function answeredBadge(p) {
  return p.answered_at ? el("span", { class: "badge" }, `Answered ${p.answered_at}`) : null;
}

// ---------- my list ----------
function renderMine(prayers) {
  const list = $("my-prayers");
  if (!prayers.length) {
    list.replaceChildren(el("li", { class: "muted" }, "No prayers yet. Add your first request above."));
    return;
  }
  list.replaceChildren(...prayers.map((p) => {
    const li = el("li", { class: p.answered_at ? "answered" : "" });
    // Wrapped in el() because the browser's replaceChildren turns a null child into the text "null".
    const view = () => li.replaceChildren(el("div", { class: "stack-tight" },
      el("div", { class: "row" }, el("span", { class: "prayer-title" }, p.title), answeredBadge(p)),
      p.body ? el("div", { class: "muted" }, p.body) : null,
      el("div", { class: "row" },
        el("button", { onclick: async () => renderMine(await api("PATCH", `/api/prayers/${p.id}`, { answered: !p.answered_at, today: localISO() })) },
          p.answered_at ? "Still praying" : "Mark answered"),
        el("button", { onclick: edit }, "Edit"),
        el("button", { class: "danger", onclick: async () => {
          if (confirm("Remove this prayer from your list?")) renderMine(await api("DELETE", `/api/prayers/${p.id}`));
        } }, "Remove"))));
    const edit = () => {
      const t = el("input", { value: p.title, maxlength: 200 });
      const b = el("input", { value: p.body, maxlength: 5000, placeholder: "Details" });
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

// ---------- lists shared with me (live) ----------
async function loadShared() {
  const lists = await api("GET", "/api/prayers/shared");
  $("refreshed").textContent = `Updated ${new Date().toLocaleTimeString()} · refreshes automatically`;
  if (!lists.length) {
    $("shared-lists").replaceChildren(el("p", { class: "muted" },
      "No one is sharing a prayer list with you yet. When someone in one of your chats turns on sharing, their list shows up here."));
    return;
  }
  $("shared-lists").replaceChildren(...lists.map((l) => el("div", {},
    el("h3", {}, `${l.owner} `, el("span", { class: "muted" }, `@${l.username}`)),
    l.prayers.length
      ? el("ul", { class: "list" }, l.prayers.map((p) => el("li", { class: p.answered_at ? "answered" : "" },
          el("div", { class: "row" }, el("span", { class: "prayer-title" }, p.title), answeredBadge(p)),
          p.body ? el("div", { class: "muted" }, p.body) : null)))
      : el("p", { class: "muted" }, "No requests right now."))));
}

(async () => {
  await initPage();
  renderMine(await api("GET", "/api/prayers"));
  await loadShared();
  setInterval(() => { if (!document.hidden) loadShared(); }, REFRESH_MS);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) loadShared(); });
})();
