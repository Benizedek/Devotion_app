// The top bar on every logged-in page: tabs, unread badge, and the profile menu.
import { api } from "./api.js";
import { el } from "./dom.js";
import { applyPrefs } from "./prefs.js";

const TABS = [["/dashboard", "Dashboard"], ["/calendar", "Devotions"], ["/prayers", "Prayer list"], ["/chat", "Chat"]];

// Call first on every logged-in page. Checks you're logged in, draws the header, returns you.
export async function initPage() {
  const me = await api("GET", "/api/me");
  applyPrefs(me);
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
    el("nav", { class: "nav" }, TABS.map(([href, label]) =>
      el("a", { href, class: here === href || here.startsWith(href + "/") ? "active" : "" }, label,
        href === "/chat" ? el("span", { id: "nav-unread", class: "nav-badge hidden" }) : null))),
    el("div", { class: "profile" }, profileBtn, menu));
  document.body.prepend(header);
  refreshUnread();
  setInterval(() => { if (!document.hidden) refreshUnread(); }, 15_000);
  return me;
}

// Update the red unread count on the Chat tab. Pass the chat list if you already have it.
export async function refreshUnread(conversations) {
  const convs = conversations ?? await api("GET", "/api/conversations").catch(() => []);
  const n = convs.reduce((sum, c) => sum + c.unread, 0);
  const badge = document.getElementById("nav-unread");
  if (!badge) return;
  badge.textContent = n > 99 ? "99+" : n;
  badge.classList.toggle("hidden", n === 0);
}
