import { api } from "../lib/api.js";
import { el, $, toast } from "../lib/dom.js";
import { localISO, prettyDate, utcDate, monthKey } from "../lib/dates.js";
import { initPage } from "../lib/header.js";
import { devotionView, monthGrid } from "../lib/widgets.js";

const FIELDS = ["scripture", "observations", "interpretation", "application"];
const today = localISO();
const state = {
  year: new Date().getFullYear(),
  month: new Date().getMonth(),      // 0-based
  selected: today,
  devotion: null,                    // the selected day's saved devotion, or null
  editing: false,                    // true while the form is open (today only)
  done: new Set(),                   // dates that have a devotion, for the visible month
  dirty: false,
};

async function loadMonth() {
  state.done = new Set(await api("GET", `/api/devotions?month=${monthKey(state.year, state.month)}`));
  renderCalendar();
}

function renderCalendar() {
  $("month-label").textContent = new Date(state.year, state.month, 1)
    .toLocaleDateString(undefined, { month: "long", year: "numeric" });
  $("cal").replaceChildren(...monthGrid({ ...state, onSelect: selectDay }));
}

function confirmLeave() {
  return !state.dirty || confirm("You have unsaved changes to today's devotion. Discard them?");
}

async function selectDay(iso) {
  if (!confirmLeave()) return;
  state.selected = iso;
  renderCalendar();
  await loadDevotion();
  $("editor").scrollIntoView({ behavior: "smooth", block: "start" });
}

async function loadDevotion() {
  state.devotion = await api("GET", `/api/devotions/${state.selected}`);
  // Today with nothing written yet opens straight into the form.
  state.editing = state.selected === today && !state.devotion;
  render();
}

// One place decides what the box shows: read-only view, or the form.
function render() {
  const d = state.devotion;
  const isToday = state.selected === today;
  $("editor-date").textContent = isToday ? `Today · ${prettyDate(today)}` : prettyDate(state.selected);
  $("today-btn").classList.toggle("hidden", isToday);
  $("edit-btn").classList.toggle("hidden", !isToday || !d || state.editing);
  $("edit-view").classList.toggle("hidden", !state.editing);
  $("read-view").classList.toggle("hidden", state.editing);
  $("visible-to").classList.toggle("hidden", !isToday);
  state.dirty = false;

  if (state.editing) {
    for (const f of FIELDS) $(f).value = d?.[f] ?? "";
    $("editor-error").textContent = "";
    $("cancel").classList.toggle("hidden", !d);
    $("delete").classList.toggle("hidden", !d);
    $("editor-status").textContent = d ? "Editing" : "Not written yet";
    return;
  }
  if (d) {
    $("editor-status").textContent = isToday
      ? `Saved · last edited ${utcDate(d.updated_at).toLocaleString()}`
      : "Read-only · past devotions can't be edited";
    $("read-view").replaceChildren(devotionView(d));
  } else {
    $("editor-status").textContent = "";
    $("read-view").replaceChildren(el("p", { class: "muted" }, "No devotion written this day."));
  }
}

function startEditing() {
  state.editing = true;
  render();
  $("observations").focus();
}

async function renderVisibleTo() {
  const chats = await api("GET", "/api/devotions/visible-to");
  $("visible-to").replaceChildren(chats.length
    ? `Shared with: ${chats.map((c) => c.title).join(", ")}. `
    : "Only you can see your devotions. ",
    el("a", { href: "/permissions" }, "Manage permissions"));
}

$("save").addEventListener("click", async () => {
  $("editor-error").textContent = "";
  try {
    const body = Object.fromEntries(FIELDS.map((f) => [f, $(f).value]));
    state.devotion = await api("PUT", `/api/devotions/${today}`, { ...body, today });
    state.editing = false;      // saved → back to read-only
    render();
    toast("Saved");
    await loadMonth();
  } catch (e) { $("editor-error").textContent = e.message; }
});

$("cancel").addEventListener("click", () => {
  if (!confirmLeave()) return;
  state.editing = false;
  render();
});

$("delete").addEventListener("click", async () => {
  if (!confirm("Delete today's devotion? It will also disappear from your chats.")) return;
  await api("DELETE", `/api/devotions/${today}`, { today });
  await Promise.all([loadDevotion(), loadMonth()]);
  toast("Deleted");
});

$("edit-btn").addEventListener("click", startEditing);

$("today-btn").addEventListener("click", () => {
  state.year = new Date().getFullYear();
  state.month = new Date().getMonth();
  loadMonth().then(() => selectDay(today));
});

for (const f of FIELDS) $(f).addEventListener("input", () => { state.dirty = true; });
window.addEventListener("beforeunload", (e) => { if (state.dirty) e.preventDefault(); });

$("prev").addEventListener("click", () => {
  state.month--; if (state.month < 0) { state.month = 11; state.year--; } loadMonth();
});
$("next").addEventListener("click", () => {
  state.month++; if (state.month > 11) { state.month = 0; state.year++; } loadMonth();
});

(async () => {
  await initPage();
  await Promise.all([loadMonth(), loadDevotion(), renderVisibleTo()]);
  // The dashboard's Edit button links here with ?edit=1
  if (new URLSearchParams(location.search).get("edit") === "1" && state.devotion) startEditing();
})();
