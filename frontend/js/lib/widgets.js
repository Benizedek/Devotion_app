// Reusable pieces of UI built from el().
import { localISO } from "./dates.js";
import { el, toast } from "./dom.js";

// An on/off switch built on a real checkbox, so keyboards and screen readers work.
// onChange(checked) should return a promise; if it throws, the switch flips back.
export function switchEl(checked, onChange, label) {
  const input = el("input", { type: "checkbox", role: "switch", checked, "aria-label": label });
  input.addEventListener("change", async () => {
    input.disabled = true;
    try { await onChange(input.checked); }
    catch (e) { input.checked = !input.checked; toast(e.message); }
    finally { input.disabled = false; }
  });
  return el("span", { class: "switch" }, input, el("span", { class: "slider", "aria-hidden": "true" }));
}

// The month calendar grid, used on your Devotions page and on other people's pages.
// done = Set of "YYYY-MM-DD" days that have a devotion; onSelect(day) runs when a day is clicked.
export function monthGrid({ year, month, done, selected, onSelect }) {
  const today = localISO();
  const first = new Date(year, month, 1);
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const cells = ["S", "M", "T", "W", "T", "F", "S"].map((d) => el("div", { class: "dow" }, d));
  for (let i = 0; i < first.getDay(); i++) cells.push(el("div", { class: "day blank" }));
  for (let d = 1; d <= daysInMonth; d++) {
    const iso = localISO(new Date(year, month, d));
    const future = iso > today;
    const classes = ["day", done.has(iso) && "done", iso === today && "today",
                     iso === selected && "selected", future && "future"].filter(Boolean);
    cells.push(el("button", {
      class: classes.join(" "), disabled: future,
      "aria-label": `${iso}${done.has(iso) ? ", devotion written" : ""}`,
      onclick: () => onSelect(iso),
    }, d));
  }
  return cells;
}

const DEVOTION_SECTIONS = [["observations", "Observations"], ["interpretation", "Interpretation"], ["application", "Application"]];

// Read-only devotion: Scripture as the heading, then whichever O/I/A sections were written.
export function devotionView(d) {
  return el("div", { class: "devotion-view" },
    d.scripture ? el("h3", {}, d.scripture) : null,
    DEVOTION_SECTIONS.filter(([key]) => d[key]).map(([key, label]) =>
      el("div", { class: "oia-block" }, el("h4", {}, label), el("p", {}, d[key]))));
}
