// Display preferences (color theme, full width). They're saved on the server so they follow you
// across devices; a copy is kept in localStorage only so the page can paint in the right colors
// before the server answers. Importing this file applies the saved copy immediately.

export function applyPrefs(prefs) {
  document.documentElement.dataset.theme = prefs.theme || "warm";
  document.documentElement.dataset.width = prefs.full_width ? "full" : "normal";
  try { localStorage.setItem("prefs", JSON.stringify({ theme: prefs.theme, full_width: prefs.full_width })); } catch {}
}

try { applyPrefs(JSON.parse(localStorage.getItem("prefs")) || {}); } catch { applyPrefs({}); }
