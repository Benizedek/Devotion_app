import { api } from "../lib/api.js";
import { el, $ } from "../lib/dom.js";
import { localISO, prettyDate, monthKey } from "../lib/dates.js";
import { initPage } from "../lib/header.js";
import { devotionView, monthGrid } from "../lib/widgets.js";

// Another person's page: their devotion calendar + devotions and/or their prayer list,
// each shown only if they share it with a chat you're both in (the server checks this).
const username = new URLSearchParams(location.search).get("u") || "";
const base = `/api/people/${encodeURIComponent(username)}`;
const today = localISO();
const state = { year: new Date().getFullYear(), month: new Date().getMonth(), selected: today, done: new Set() };

async function loadMonth() {
  state.done = new Set(await api("GET", `${base}/devotions?month=${monthKey(state.year, state.month)}`));
  $("month-label").textContent = new Date(state.year, state.month, 1)
    .toLocaleDateString(undefined, { month: "long", year: "numeric" });
  $("cal").replaceChildren(...monthGrid({ ...state, onSelect: selectDay }));
}

async function selectDay(iso) {
  state.selected = iso;
  await Promise.all([loadMonth(), loadDevotion()]);
}

async function loadDevotion() {
  const d = await api("GET", `${base}/devotions/${state.selected}`);
  $("devotion-date").textContent = state.selected === today ? `Today · ${prettyDate(today)}` : prettyDate(state.selected);
  $("devotion-body").replaceChildren(d ? devotionView(d) : el("p", { class: "muted" }, "No devotion this day."));
}

async function loadPrayers() {
  const prayers = await api("GET", `${base}/prayers`);
  $("prayers").replaceChildren(...(prayers.length
    ? prayers.map((p) => el("li", {}, el("span", { class: "prayer-title" }, p.title),
        p.body ? el("div", { class: "muted" }, p.body) : null))
    : [el("li", { class: "muted" }, "No requests right now.")]));
}

$("prev").addEventListener("click", () => {
  state.month--; if (state.month < 0) { state.month = 11; state.year--; } loadMonth();
});
$("next").addEventListener("click", () => {
  state.month++; if (state.month > 11) { state.month = 0; state.year++; } loadMonth();
});
if (history.length > 1) {
  $("back-link").addEventListener("click", (e) => { e.preventDefault(); history.back(); });
}

(async () => {
  await initPage();
  let p;
  try {
    p = await api("GET", base);
  } catch (e) {
    $("name").textContent = "Not found";
    $("handle").textContent = e.message;
    return;
  }
  if (p.is_me) { location.href = "/calendar"; return; }
  document.title = `${p.display_name} · Daily Bread`;
  $("name").textContent = p.display_name;
  $("handle").textContent = `@${p.username}`;

  if (!p.can_see_devotions && !p.can_see_prayers) {
    $("nothing").textContent = `${p.display_name} isn't sharing their devotions or prayer list with you.`;
    $("nothing").classList.remove("hidden");
    return;
  }
  const jobs = [];
  if (p.can_see_devotions) {
    $("devotions-col").classList.remove("hidden");
    jobs.push(loadMonth(), loadDevotion());
  }
  if (p.can_see_prayers) {
    $("prayers-card").classList.remove("hidden");
    jobs.push(loadPrayers());
  }
  await Promise.all(jobs);
})();
