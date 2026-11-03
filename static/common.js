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

// Header + login check shared by every logged-in page.
async function initPage() {
  const me = await api("GET", "/api/me");
  const links = [["/dashboard", "Dashboard"], ["/calendar", "Devotions"], ["/prayers", "Prayer list"],
                 ["/shared", "Shared with me"], ["/groups", "Groups"]];
  const header = el("header", { class: "topbar" },
    el("a", { class: "brand", href: "/dashboard" }, "Daily Bread"),
    el("nav", { class: "nav" }, links.map(([href, label]) =>
      el("a", { href, class: location.pathname === href ? "active" : "" }, label,
        href === "/shared" ? el("span", { id: "nav-unread", class: "nav-badge hidden" }) : null))),
    el("span", { class: "who" }, `${me.display_name} · @${me.username}`),
    el("button", { onclick: async () => { await api("POST", "/api/logout"); location.href = "/"; } }, "Log out"));
  document.body.prepend(header);
  refreshUnread();
  setInterval(() => { if (!document.hidden) refreshUnread(); }, 15_000);
  return me;
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
