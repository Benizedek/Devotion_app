// People picker. Two modes:
//   /groups          → pick people, then start a 1-on-1 chat or a group
//   /groups?add=ID   → add people to an existing group chat
const $ = (id) => document.getElementById(id);
const addTo = Number(new URLSearchParams(location.search).get("add")) || null;
const selected = new Map();        // user id -> user
let alreadyIn = new Set();         // member ids when adding to an existing group
let searchTimer;
let lastResults = [];

function renderSelected() {
  $("selected").replaceChildren(...[...selected.values()].map((u) =>
    el("span", { class: "pill" }, u.display_name,
      el("button", { "aria-label": `Remove ${u.display_name}`, onclick: () => toggle(u) }, "×"))));
  const n = selected.size;
  $("go").disabled = n === 0;
  if (addTo) {
    $("go").textContent = n ? `Add ${n} ${n === 1 ? "person" : "people"}` : "Add people";
  } else {
    $("go").textContent = n > 1 ? "Create group" : "Start chat";
    $("name-row").classList.toggle("hidden", n < 2);
  }
}

function renderResults(users, q) {
  lastResults = users;
  if (q.length < 2) { $("results").replaceChildren(); return; }
  if (!users.length) {
    $("results").replaceChildren(el("li", { class: "muted" }, `No one found for “${q}”. They may need to sign up first.`));
    return;
  }
  $("results").replaceChildren(...users.map((u) => {
    const inGroup = alreadyIn.has(u.id);
    const picked = selected.has(u.id);
    return el("li", { class: "person" },
      el("div", {}, el("strong", {}, u.display_name), " ", el("span", { class: "muted" }, `@${u.username}`)),
      inGroup
        ? el("span", { class: "muted small" }, "Already in group")
        : el("button", { class: picked ? "" : "primary", onclick: () => toggle(u) }, picked ? "Added ✓" : "Add"));
  }));
}

function toggle(u) {
  if (selected.has(u.id)) selected.delete(u.id); else selected.set(u.id, u);
  renderSelected();
  renderResults(lastResults, $("search").value.trim());
}

$("search").addEventListener("input", () => {
  clearTimeout(searchTimer);
  const q = $("search").value.trim();
  searchTimer = setTimeout(async () => {
    const users = q.length < 2 ? [] : await api("GET", `/api/users/search?q=${encodeURIComponent(q)}`);
    if (q === $("search").value.trim()) renderResults(users, q);   // ignore out-of-date responses
  }, 250);
});

$("go").addEventListener("click", async () => {
  $("error").textContent = "";
  $("go").disabled = true;
  const user_ids = [...selected.keys()];
  try {
    if (addTo) {
      await api("POST", `/api/conversations/${addTo}/members`, { user_ids });
      location.href = `/chat?c=${addTo}`;
    } else {
      const { id } = await api("POST", "/api/conversations", { user_ids, name: $("group-name").value });
      location.href = `/chat?c=${id}`;
    }
  } catch (e) {
    $("error").textContent = e.message;
    $("go").disabled = false;
  }
});

(async () => {
  await initPage();
  if (addTo) {
    try {
      const conv = await api("GET", `/api/conversations/${addTo}`);
      alreadyIn = new Set(conv.members.map((m) => m.id));
      $("heading").textContent = `Add people to ${conv.title}`;
      $("sub").textContent = "They'll see the group's messages from now on.";
    } catch {
      location.href = "/groups";
      return;
    }
  }
  renderSelected();
  $("search").focus();
})();
