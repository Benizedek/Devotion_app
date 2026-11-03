const $ = (id) => document.getElementById(id);
const FIELDS = ["scripture", "observations", "interpretation", "application"];
const today = localISO();
const state = {
  year: new Date().getFullYear(),
  month: new Date().getMonth(),      // 0-based
  selected: today,
  done: new Set(),                   // dates that have a devotion, for the visible month
  dirty: false,
};

async function loadMonth() {
  const monthKey = `${state.year}-${String(state.month + 1).padStart(2, "0")}`;
  state.done = new Set(await api("GET", `/api/devotions?month=${monthKey}`));
  renderCalendar();
}

function renderCalendar() {
  const first = new Date(state.year, state.month, 1);
  const daysInMonth = new Date(state.year, state.month + 1, 0).getDate();
  $("month-label").textContent = first.toLocaleDateString(undefined, { month: "long", year: "numeric" });

  const cells = ["S", "M", "T", "W", "T", "F", "S"].map((d) => el("div", { class: "dow" }, d));
  for (let i = 0; i < first.getDay(); i++) cells.push(el("div", { class: "day blank" }));
  for (let d = 1; d <= daysInMonth; d++) {
    const iso = localISO(new Date(state.year, state.month, d));
    const classes = ["day"];
    if (state.done.has(iso)) classes.push("done");
    if (iso === today) classes.push("today");
    if (iso === state.selected) classes.push("selected");
    const future = iso > today;
    if (future) classes.push("future");
    cells.push(el("button", {
      class: classes.join(" "), disabled: future,
      "aria-label": `${iso}${state.done.has(iso) ? ", devotion written" : ""}`,
      onclick: () => selectDay(iso),
    }, d));
  }
  $("cal").replaceChildren(...cells);
}

async function selectDay(iso) {
  if (state.dirty && !confirm("You have unsaved changes. Leave this day anyway?")) return;
  state.selected = iso;
  renderCalendar();
  await loadDevotion();
  $("editor").scrollIntoView({ behavior: "smooth", block: "start" });
}

async function loadDevotion() {
  const d = await api("GET", `/api/devotions/${state.selected}`);
  $("editor-date").textContent = prettyDate(state.selected);
  for (const f of FIELDS) $(f).value = d?.[f] ?? "";
  $("editor-error").textContent = "";
  state.dirty = false;
  renderSaved(d);
}

function renderSaved(d) {
  $("editor-status").textContent = d ? `Saved · last edited ${utcDate(d.updated_at).toLocaleString()}` : "Not written yet";
  $("delete").classList.toggle("hidden", !d);
  $("share-section").classList.toggle("hidden", !d);
  if (!d) return;
  $("sent-list").replaceChildren(
    d.sent_to.length ? "Sent to:" : el("span", { class: "muted" }, "Only you can see this devotion."),
    ...d.sent_to.map((s) => el("span", { class: "pill" }, s.label,
      el("button", { "aria-label": `Unsend from ${s.label}`, title: "Unsend", onclick: async () => {
        await api("DELETE", `/api/messages/${s.message_id}`);
        await loadDevotion();
      } }, "×"))));
}

$("save").addEventListener("click", async () => {
  $("editor-error").textContent = "";
  try {
    const body = Object.fromEntries(FIELDS.map((f) => [f, $(f).value]));
    const d = await api("PUT", `/api/devotions/${state.selected}`, body);
    state.dirty = false;
    renderSaved(d);
    toast("Saved");
    await loadMonth();
  } catch (e) { $("editor-error").textContent = e.message; }
});

$("delete").addEventListener("click", async () => {
  if (!confirm("Delete this devotion? It will also disappear from any chats you sent it to.")) return;
  await api("DELETE", `/api/devotions/${state.selected}`);
  await Promise.all([loadDevotion(), loadMonth()]);
  toast("Deleted");
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
  $("share-control").append(await chatPicker(async (convId) => {
    renderSaved(await api("POST", `/api/devotions/${state.selected}/send`, { conversation_id: convId }));
  }));
  await Promise.all([loadMonth(), loadDevotion()]);
})();
