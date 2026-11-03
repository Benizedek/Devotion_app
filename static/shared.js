const $ = (id) => document.getElementById(id);
const THREAD_POLL_MS = 4_000;    // how often the open chat checks for new messages
const LIST_POLL_MS = 10_000;     // how often the chat list refreshes

const state = { me: null, convs: [], current: null, conv: null, lastId: 0, loading: false };

// ---------- chat list ----------
async function loadConvs() {
  state.convs = await api("GET", "/api/conversations");
  refreshUnread(state.convs);
  const list = $("conv-list");
  if (!state.convs.length) {
    list.replaceChildren(el("li", { class: "conv-empty muted" },
      "No chats yet. ", el("a", { href: "/groups" }, "Start one"), " with a friend or your small group."));
    return;
  }
  list.replaceChildren(...state.convs.map((c) => el("li", {},
    el("button", { class: `conv${c.id === state.current ? " active" : ""}`, onclick: () => openConv(c.id) },
      el("div", { class: "conv-top" },
        el("strong", { class: "conv-title" }, c.title),
        el("span", { class: "muted small" }, shortTime(c.last_at))),
      el("div", { class: "conv-bottom" },
        el("span", { class: `conv-preview${c.unread ? " unread" : ""}` },
          c.preview || (c.is_group ? `${c.member_count} members` : "Say hello")),
        c.unread ? el("span", { class: "nav-badge" }, c.unread) : null)))));
}

// ---------- one chat ----------
async function openConv(id) {
  state.current = id;
  state.lastId = 0;
  history.replaceState(null, "", `/chat?c=${id}`);
  $("layout").classList.add("show-thread");
  $("thread-empty").classList.add("hidden");
  $("thread-body").classList.remove("hidden");
  closeSettings();
  $("messages").replaceChildren();
  try {
    state.conv = await api("GET", `/api/conversations/${id}`);
  } catch (e) {
    toast(e.message);
    closeConv();
    return;
  }
  renderThreadHeader();
  await loadMessages(true);
  loadConvs();          // clears the unread badge for this chat
  $("msg-input").focus();
}

function renderThreadHeader() {
  const c = state.conv;
  $("thread-title").textContent = c.title;
  $("thread-sub").textContent = c.is_group
    ? `${c.members.length} ${c.members.length === 1 ? "member" : "members"}`
    : "@" + (c.members.find((m) => m.id !== state.me.id)?.username ?? "");
  $("share-banner").classList.toggle("hidden", c.share_devotions || c.share_prayers);
}

function closeConv() {
  state.current = null;
  state.conv = null;
  history.replaceState(null, "", "/chat");
  $("layout").classList.remove("show-thread");
  $("thread-body").classList.add("hidden");
  $("thread-empty").classList.remove("hidden");
  loadConvs();
}

async function loadMessages(scrollToEnd = false) {
  if (!state.current || state.loading) return;
  state.loading = true;
  const id = state.current;
  try {
    const msgs = await api("GET", `/api/conversations/${id}/messages?after=${state.lastId}`);
    if (id !== state.current || !msgs.length) return;   // user switched chats mid-request, or nothing new
    const box = $("messages");
    const nearBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 80;
    box.append(...msgs.map(renderMessage));
    state.lastId = msgs[msgs.length - 1].id;
    if (scrollToEnd || nearBottom) box.scrollTop = box.scrollHeight;
  } finally {
    state.loading = false;
  }
}

function renderMessage(m) {
  if (m.kind === "system") return el("div", { class: "msg system" }, m.body);

  let content;
  if (m.kind === "devotion") {
    if (m.devotion_status === "shown") {
      content = el("div", { class: "devotion-card" },
        el("div", { class: "muted small" }, `${m.mine ? "Your" : m.sender + "'s"} devotion · ${prettyDate(m.devotion.entry_date)}`),
        devotionView(m.devotion));
    } else {
      content = el("div", { class: "bubble faded" }, m.devotion_status === "deleted"
        ? "This devotion was deleted."
        : `${m.sender} is no longer sharing devotions here.`);
    }
  } else {
    content = el("div", { class: "bubble" }, m.body);
  }

  const node = el("div", { class: `msg${m.mine ? " mine" : ""}` },
    el("div", { class: "msg-meta" },
      state.conv?.is_group && !m.mine ? `${m.sender} · ` : "",
      shortTime(m.created_at),
      m.mine && m.kind === "text" ? el("button", { class: "link unsend", onclick: async () => {
        if (!confirm("Unsend this message?")) return;
        await api("DELETE", `/api/messages/${m.id}`);
        node.remove();
      } }, "Unsend") : null),
    content);
  return node;
}

// ---------- chat settings panel ----------
function renderSettings() {
  const c = state.conv;

  // Two independent switches: devotions and prayers.
  const shareSetting = (key, title, onText, offText) => el("div", { class: "setting" },
    el("div", { class: "setting-label" },
      el("strong", {}, title),
      el("span", { class: "muted small" }, c[key] ? onText : offText)),
    switchEl(c[key], async (on) => {
      state.conv = await api("PATCH", `/api/conversations/${c.id}/settings`, { [key]: on, today: localISO() });
      renderThreadHeader();
      renderSettings();
      await loadMessages(true);
    }, title));

  const sharingText = (m) => {
    const parts = [m.share_devotions && "devotions", m.share_prayers && "prayers"].filter(Boolean);
    return parts.length ? `Sharing ${parts.join(" & ")}` : "Not sharing";
  };
  const memberRow = (m) => el("li", { class: "person" },
    el("div", {},
      m.id === state.me.id
        ? el("strong", {}, m.display_name)
        : el("a", { class: "person-link", href: `/person?u=${encodeURIComponent(m.username)}`,
            title: `See what ${m.display_name} shares` }, m.display_name),
      " ", el("span", { class: "muted" }, `@${m.username}`),
      m.id === state.me.id ? el("span", { class: "muted" }, " (you)") : null,
      el("div", { class: "row small" },
        m.is_admin ? el("span", { class: "badge" }, "Creator") : null,
        el("span", { class: "muted" }, sharingText(m)))),
    c.is_admin && m.id !== state.me.id
      ? el("button", { class: "danger", onclick: async () => {
          if (!confirm(`Remove ${m.display_name} from ${c.title}?`)) return;
          try {
            state.conv = await api("DELETE", `/api/conversations/${c.id}/members/${m.id}`);
            renderThreadHeader();
            renderSettings();
            loadMessages();
          } catch (e) { toast(e.message); }
        } }, "Remove")
      : null);

  $("settings").replaceChildren(
    el("div", { class: "stack" },
      shareSetting("share_devotions", "Share my devotions",
        "This chat can see your devotion calendar and past devotions, and each day's devotion is posted here.",
        "Off: this chat can't see your devotions."),
      shareSetting("share_prayers", "Share my prayer list",
        "This chat sees your prayer list live under Praying for others.",
        "Off: this chat can't see your prayer list."),
      el("div", {},
        el("div", { class: "card-head" },
          el("h3", {}, c.is_group ? `Members (${c.members.length})` : "Chat with"),
          c.is_group ? el("a", { class: "button-link", href: `/groups?add=${c.id}` }, "+ Add people") : null),
        el("ul", { class: "list" }, c.members.map(memberRow))),
      c.is_group
        ? el("div", {}, el("button", { class: "danger", onclick: async () => {
            if (!confirm(`Leave ${c.title}? You'll stop seeing its messages and shared prayer lists.`)) return;
            await api("POST", `/api/conversations/${c.id}/leave`);
            closeConv();
          } }, "Leave group"))
        : el("p", { class: "muted small" }, "Want more people? Use “+ New” in your chat list to start a group.")));
}

function openSettings() {
  renderSettings();
  $("settings").classList.remove("hidden");
  $("settings-btn").setAttribute("aria-expanded", "true");
}

function closeSettings() {
  $("settings").classList.add("hidden");
  $("settings-btn").setAttribute("aria-expanded", "false");
}

$("settings-btn").addEventListener("click", () =>
  $("settings").classList.contains("hidden") ? openSettings() : closeSettings());
$("banner-settings").addEventListener("click", openSettings);

$("back").addEventListener("click", closeConv);

$("composer").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = $("msg-input");
  const body = input.value.trim();
  if (!body || !state.current) return;
  input.value = "";
  try {
    await api("POST", `/api/conversations/${state.current}/messages`, { body });
    await loadMessages(true);
    loadConvs();
  } catch (err) {
    input.value = body;
    toast(err.message);
  }
});

(async () => {
  state.me = await initPage();
  await loadConvs();
  const fromUrl = Number(new URLSearchParams(location.search).get("c"));
  if (fromUrl) await openConv(fromUrl);
  setInterval(() => { if (!document.hidden) loadMessages(); }, THREAD_POLL_MS);
  setInterval(() => { if (!document.hidden) loadConvs(); }, LIST_POLL_MS);
})();
