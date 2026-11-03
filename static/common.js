// Shared helpers for every page. No frameworks, no build step.

async function api(method, path, body) {
  const opts = { method, headers: {} };
  if (method !== "GET") {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body ?? {});
  }
  const res = await fetch(path, opts);
  const data = await res.json().catch(() => ({}));
  if (res.status === 401 && location.pathname !== "/") {
    location.href = "/";
    throw new Error("Please log in");
  }
  if (!res.ok) throw new Error(data.error || "Request failed");
  return data;
}

// Build DOM safely: text always goes through textContent, so user content can't inject HTML.
function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else if (v === true) node.setAttribute(k, "");
    else if (v !== false && v != null) node.setAttribute(k, v);
  }
  for (const c of children.flat()) {
    if (c == null || c === false) continue;
    node.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return node;
}

// Local calendar date, so a devotion written at 11pm in Seoul counts for that day there.
function localISO(d = new Date()) {
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

function prettyDate(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(undefined,
    { weekday: "long", month: "long", day: "numeric", year: "numeric" });
}

// SQLite stores "YYYY-MM-DD HH:MM:SS" in UTC. Safari can't parse the space, so swap in a "T".
function utcDate(sqliteTime) {
  return new Date(sqliteTime.replace(" ", "T") + "Z");
}

function shortTime(sqliteTime) {
  const d = utcDate(sqliteTime);
  const time = d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  return d.toDateString() === new Date().toDateString()
    ? time
    : `${d.toLocaleDateString([], { month: "short", day: "numeric" })}, ${time}`;
}

function toast(msg) {
  let t = document.querySelector(".toast");
  if (!t) { t = el("div", { class: "toast" }); document.body.append(t); }
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(t._timer);
  t._timer = setTimeout(() => t.classList.remove("show"), 2200);
}

// ---------- display preferences (color theme, full width) ----------
// Saved on the server so they follow you across devices. A copy is kept in localStorage
// only so the page can paint in the right colors before the server answers.
function applyPrefs(prefs) {
  document.documentElement.dataset.theme = prefs.theme || "warm";
  document.documentElement.dataset.width = prefs.full_width ? "full" : "normal";
  try { localStorage.setItem("prefs", JSON.stringify({ theme: prefs.theme, full_width: prefs.full_width })); } catch {}
}
try { applyPrefs(JSON.parse(localStorage.getItem("prefs")) || {}); } catch { applyPrefs({}); }

// Header + login check shared by every logged-in page.
async function initPage() {
  const me = await api("GET", "/api/me");
  applyPrefs(me);
  const links = [["/dashboard", "Dashboard"], ["/calendar", "Devotions"], ["/prayers", "Prayer list"], ["/chat", "Chat"]];
  const here = location.pathname === "/shared" ? "/chat" : location.pathname;

  const menu = el("div", { class: "menu hidden", id: "profile-menu", role: "menu" },
    el("div", { class: "menu-who" }, el("strong", {}, me.display_name), el("span", { class: "muted small" }, `@${me.username}`)),
    el("a", { href: "/settings", role: "menuitem" }, "Settings"),
    el("a", { href: "/permissions", role: "menuitem" }, "Permissions"),
    el("hr"),
    el("button", { role: "menuitem", onclick: async () => { await api("POST", "/api/logout"); location.href = "/"; } }, "Log out"));
  const profileBtn = el("button", { class: "profile-btn", "aria-haspopup": "menu", "aria-expanded": "false",
    "aria-controls": "profile-menu" }, me.display_name, el("span", { "aria-hidden": "true" }, " ▾"));
  const setMenu = (open) => {
    menu.classList.toggle("hidden", !open);
    profileBtn.setAttribute("aria-expanded", String(open));
  };
  profileBtn.addEventListener("click", (e) => { e.stopPropagation(); setMenu(menu.classList.contains("hidden")); });
  document.addEventListener("click", (e) => { if (!menu.contains(e.target)) setMenu(false); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") setMenu(false); });

  const header = el("header", { class: "topbar" },
    el("a", { class: "brand", href: "/dashboard" }, "Daily Bread"),
    el("nav", { class: "nav" }, links.map(([href, label]) =>
      el("a", { href, class: here === href || here.startsWith(href + "/") ? "active" : "" }, label,
        href === "/chat" ? el("span", { id: "nav-unread", class: "nav-badge hidden" }) : null))),
    el("div", { class: "profile" }, profileBtn, menu));
  document.body.prepend(header);
  refreshUnread();
  setInterval(() => { if (!document.hidden) refreshUnread(); }, 15_000);
  return me;
}

// An on/off switch built on a real checkbox, so keyboards and screen readers work.
// onChange(checked) should return a promise; if it throws, the switch flips back.
function switchEl(checked, onChange, label) {
  const input = el("input", { type: "checkbox", role: "switch", checked, "aria-label": label });
  input.addEventListener("change", async () => {
    input.disabled = true;
    try { await onChange(input.checked); }
    catch (e) { input.checked = !input.checked; toast(e.message); }
    finally { input.disabled = false; }
  });
  return el("span", { class: "switch" }, input, el("span", { class: "slider", "aria-hidden": "true" }));
}

// Month grid used by your own Devotions page and by other people's pages.
function monthGrid({ year, month, done, selected, onSelect }) {
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

function monthKey(year, month) {
  return `${year}-${String(month + 1).padStart(2, "0")}`;
}

async function refreshUnread(conversations) {
  const convs = conversations ?? await api("GET", "/api/conversations").catch(() => []);
  const n = convs.reduce((sum, c) => sum + c.unread, 0);
  const badge = document.getElementById("nav-unread");
  if (!badge) return;
  badge.textContent = n > 99 ? "99+" : n;
  badge.classList.toggle("hidden", n === 0);
}

const DEVOTION_SECTIONS = [["observations", "Observations"], ["interpretation", "Interpretation"], ["application", "Application"]];

// Read-only devotion: Scripture as the heading, then whichever O/I/A sections were written.
function devotionView(d) {
  return el("div", { class: "devotion-view" },
    d.scripture ? el("h3", {}, d.scripture) : null,
    DEVOTION_SECTIONS.filter(([key]) => d[key]).map(([key, label]) =>
      el("div", { class: "oia-block" }, el("h4", {}, label), el("p", {}, d[key]))));
}
