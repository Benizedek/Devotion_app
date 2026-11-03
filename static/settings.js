const THEMES = [["warm", "Warm"], ["sage", "Sage"], ["ocean", "Ocean"], ["plum", "Plum"], ["slate", "Slate"]];

function renderThemes(current) {
  document.getElementById("themes").replaceChildren(...THEMES.map(([key, label]) =>
    el("button", {
      class: `theme-option${key === current ? " selected" : ""}`, role: "radio",
      "aria-checked": String(key === current), "data-swatch": key,
      onclick: async () => {
        const me = await api("PATCH", "/api/me/preferences", { theme: key });
        applyPrefs(me);
        renderThemes(me.theme);
      },
    }, el("span", { class: "swatch", "aria-hidden": "true" }), label)));
}

(async () => {
  const me = await initPage();
  renderThemes(me.theme);
  document.getElementById("width-switch").replaceWith(switchEl(me.full_width, async (on) => {
    applyPrefs(await api("PATCH", "/api/me/preferences", { full_width: on }));
  }, "Fill the entire page"));
})();
