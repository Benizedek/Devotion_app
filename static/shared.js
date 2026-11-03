const $ = (id) => document.getElementById(id);
const THREAD_POLL_MS = 4_000;    // how often the open chat checks for new messages
const LIST_POLL_MS = 10_000;     // how often the chat list refreshes
const SECTIONS = [["observations", "Observations"], ["interpretation", "Interpretation"], ["application", "Application"]];

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
  history.replaceState(null, "", `/shared?c=${id}`);
  $("layout").classList.add("show-thread");
  $("thread-empty").classList.add("hidden");
  $("thread-body").classList.remove("hidden");
  $("info").classList.add("hidden");
  $("messages").replaceChildren();
  try {
    state.conv = await api("GET", `/api/conversations/${id}`);
  } catch (e) {
    toast(e.message);
    closeConv();
    return;
  }
  $("thread-title").textContent = state.conv.title;
  $("thread-sub").textContent = state.conv.is_group
    ? `${state.conv.members.length} members`
    : "@" + (state.conv.members.find((m) => m.id !== state.me.id)?.username ?? "");
  await loadMessages(true);
  loadConvs();          // clears the unread badge for this chat
  $("msg-input").focus();
}

function closeConv() {
  state.current = null;
  state.conv = null;
  history.replaceState(null, "", "/shared");
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
    const d = m.devotion;
    content = d
      ? el("div", { class: "devotion-card" },
          el("div", { class: "muted small" }, `${m.mine ? "Your" : m.sender + "'s"} devotion · ${prettyDate(d.entry_date)}`),
          d.scripture ? el("h3", {}, d.scripture) : null,
          SECTIONS.filter(([key]) => d[key]).map(([key, label]) =>
            el("div", { class: "oia-block" }, el("h4", {}, label), el("p", {}, d[key]))))
      : el("div", { class: "bubble muted" }, "This devotion was deleted.");
  } else if (m.kind === "prayer_list") {
    content = el("div", { class: "bubble" },
      m.mine ? "You shared your prayer list. " : `${m.sender} shared their prayer list. `,
      el("a", { href: "/prayers" }, m.mine ? "Manage" : "Pray for them"));
  } else {
    content = el("div", { class: "bubble" }, m.body);
  }

  const node = el("div", { class: `msg${m.mine ? " mine" : ""}` },
    el("div", { class: "msg-meta" },
      state.conv?.is_group && !m.mine ? `${m.sender} · ` : "",
      shortTime(m.created_at),
      m.mine ? el("button", { class: "link unsend", onclick: async () => {
        if (!confirm("Unsend this message?")) return;
        await api("DELETE", `/api/messages/${m.id}`);
        node.remove();
      } }, "Unsend") : null),
    content);
  return node;
}

// ---------- chat info panel ----------
function renderInfo() {
  const c = state.conv;
  $("info").replaceChildren(
    el("h3", {}, c.is_group ? "Members" : "Chat with"),
    el("ul", { class: "list" }, c.members.map((m) =>
      el("li", {}, m.display_name, " ", el("span", { class: "muted" }, `@${m.username}`),
        m.id === state.me.id ? el("span", { class: "muted" }, " (you)") : null))),
    c.is_group
      ? el("div", { class: "row" },
          el("a", { class: "button-link", href: `/groups?add=${c.id}` }, "+ Add people"),
          el("button", { class: "danger", onclick: async () => {
            if (!confirm(`Leave ${c.title}? You'll stop seeing its messages and shared prayer lists.`)) return;
            await api("POST", `/api/conversations/${c.id}/leave`);
            closeConv();
          } }, "Leave group"))
      : el("p", { class: "muted small" }, "Want more people? Start a group from the Groups tab."));
}

$("info-btn").addEventListener("click", () => {
  const info = $("info");
  if (info.classList.contains("hidden")) renderInfo();
  info.classList.toggle("hidden");
});

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
