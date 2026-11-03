const $ = (id) => document.getElementById(id);
const today = localISO();
const state = {
  year: new Date().getFullYear(),
  month: new Date().getMonth(),      // 0-based
  selected: today,
  done: new Set(),                   // dates that have a devotion, for the visible month
  dirty: false,
};

async function loadStats() {
  const s = await api("GET", `/api/devotions/stats?today=${today}`);
  const box = $("stats");
  box.replaceChildren(
    ...[[s.current_streak, "day streak"], [s.longest_streak, "longest streak"],
        [`${s.last_30_days}/30`, "last 30 days"], [s.total, "total devotions"]]
      .map(([n, label]) => el("div", { class: "stat" }, el("b", {}, n), el("span", {}, label))));
}

async function loadMonth() {
  const monthKey = `${state.year}-${String(state.month + 1).padStart(2, "0")}`;
  const rows = await api("GET", `/api/devotions?month=${monthKey}`);
  state.done = new Set(rows.map((r) => r.entry_date));
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
}

async function loadDevotion() {
  const d = await api("GET", `/api/devotions/${state.selected}`);
  $("editor-date").textContent = prettyDate(state.selected);
  $("title").value = d?.title ?? "";
  $("scripture").value = d?.scripture ?? "";
  $("body").value = d?.body ?? "";
  $("editor-error").textContent = "";
  state.dirty = false;
  renderSaved(d);
}

function renderSaved(d) {
  $("editor-status").textContent = d ? `Saved · last edited ${new Date(d.updated_at + "Z").toLocaleString()}` : "Not written yet";
  $("delete").classList.toggle("hidden", !d);
  $("share-section").classList.toggle("hidden", !d);
  if (!d) return;
  $("share-list").replaceChildren(
    d.shares.length ? "" : el("span", { class: "muted" }, "Only you can see this devotion."),
    ...d.shares.map((s) => el("span", { class: "pill" }, s.label,
      el("button", { "aria-label": `Stop sharing with ${s.label}`, onclick: async () => {
        await api("DELETE", `/api/devotion-shares/${s.id}`);
        await loadDevotion();
      } }, "×"))));
}

$("save").addEventListener("click", async () => {
  $("editor-error").textContent = "";
  try {
    const d = await api("PUT", `/api/devotions/${state.selected}`, {
      title: $("title").value, scripture: $("scripture").value, body: $("body").value,
    });
    state.dirty = false;
    renderSaved(d);
    toast("Saved");
    await Promise.all([loadMonth(), loadStats()]);
  } catch (e) { $("editor-error").textContent = e.message; }
});

$("delete").addEventListener("click", async () => {
  if (!confirm("Delete this devotion? This can't be undone.")) return;
  await api("DELETE", `/api/devotions/${state.selected}`);
  await Promise.all([loadDevotion(), loadMonth(), loadStats()]);
  toast("Deleted");
});

for (const id of ["title", "scripture", "body"]) $(id).addEventListener("input", () => { state.dirty = true; });
window.addEventListener("beforeunload", (e) => { if (state.dirty) e.preventDefault(); });

$("prev").addEventListener("click", () => {
  state.month--; if (state.month < 0) { state.month = 11; state.year--; } loadMonth();
});
$("next").addEventListener("click", () => {
  state.month++; if (state.month > 11) { state.month = 0; state.year++; } loadMonth();
});

(async () => {
  await initPage();
  $("share-control").append(await shareControl(async (target) => {
    await api("POST", `/api/devotions/${state.selected}/shares`, target);
    await loadDevotion();
  }));
  await Promise.all([loadMonth(), loadStats(), loadDevotion()]);
})();
