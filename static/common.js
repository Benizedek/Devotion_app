// Shared helpers for every page. No frameworks, no build step.

async function api(method, path, body) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  } else if (method !== "GET") {
    opts.headers["Content-Type"] = "application/json";
    opts.body = "{}";
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
  const links = [["/dashboard", "Dashboard"], ["/calendar", "Devotions"], ["/prayers", "Prayer list"], ["/shared", "Shared with me"], ["/groups", "Groups"]];
  const header = el("header", { class: "topbar" },
    el("a", { class: "brand", href: "/dashboard" }, "Daily Bread"),
    el("nav", { class: "nav" }, links.map(([href, label]) =>
      el("a", { href, class: location.pathname === href ? "active" : "" }, label))),
    el("span", { class: "who" }, `${me.display_name} · @${me.username}`),
    el("button", { onclick: async () => { await api("POST", "/api/logout"); location.href = "/"; } }, "Log out"));
  document.body.prepend(header);
  return me;
}

// Reusable "share with a person or group" control.
// onShare receives {username} or {group_id}.
async function shareControl(onShare) {
  const groups = await api("GET", "/api/groups");
  const select = el("select", {},
    el("option", { value: "" }, "Choose a group…"),
    groups.map((g) => el("option", { value: g.id }, g.name)));
  const userInput = el("input", { placeholder: "or a username", autocomplete: "off" });
  const err = el("div", { class: "error" });
  const btn = el("button", { class: "primary", onclick: async () => {
    err.textContent = "";
    const target = userInput.value.trim()
      ? { username: userInput.value.trim() }
      : select.value ? { group_id: Number(select.value) } : null;
    if (!target) { err.textContent = "Pick a group or type a username."; return; }
    try { await onShare(target); userInput.value = ""; select.value = ""; toast("Shared"); }
    catch (e) { err.textContent = e.message; }
  } }, "Share");
  return el("div", {}, el("div", { class: "row" }, select, userInput, btn), err);
}
