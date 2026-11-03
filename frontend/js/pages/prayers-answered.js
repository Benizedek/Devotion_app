import { api } from "../lib/api.js";
import { el, toast } from "../lib/dom.js";
import { initPage } from "../lib/header.js";

function prettyShort(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(undefined, { month: "long", day: "numeric", year: "numeric" });
}

function render(all) {
  const answered = all.filter((p) => p.answered_at)
    .sort((a, b) => b.answered_at.localeCompare(a.answered_at));   // most recently answered first
  const list = document.getElementById("answered");
  if (!answered.length) {
    list.replaceChildren(el("li", { class: "muted" },
      "No answered prayers yet. When you tap “Mark answered” on a prayer, it moves here."));
    return;
  }
  list.replaceChildren(...answered.map((p) => el("li", { class: "stack-tight" },
    el("div", { class: "row" },
      el("span", { class: "prayer-title" }, p.title),
      el("span", { class: "badge" }, `Answered ${prettyShort(p.answered_at)}`)),
    p.body ? el("div", { class: "muted" }, p.body) : null,
    el("div", { class: "row" },
      el("button", { onclick: async () => {
        render(await api("PATCH", `/api/prayers/${p.id}`, { answered: false }));
        toast("Moved back to your prayer list");
      } }, "Still praying"),
      el("button", { class: "danger", onclick: async () => {
        if (confirm("Delete this prayer permanently?")) render(await api("DELETE", `/api/prayers/${p.id}`));
      } }, "Delete")))));
}

(async () => {
  await initPage();
  render(await api("GET", "/api/prayers"));
})();
