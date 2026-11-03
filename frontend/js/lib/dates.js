// Dates and times. Devotion days use your *local* date so travelling across time zones works.

// Local calendar date as "YYYY-MM-DD", so a devotion written at 11pm in Seoul counts for that day there.
export function localISO(d = new Date()) {
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

// "2026-11-02" -> "Monday, November 2, 2026"
export function prettyDate(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(undefined,
    { weekday: "long", month: "long", day: "numeric", year: "numeric" });
}

// SQLite stores "YYYY-MM-DD HH:MM:SS" in UTC. Safari can't parse the space, so swap in a "T".
export function utcDate(sqliteTime) {
  return new Date(sqliteTime.replace(" ", "T") + "Z");
}

// "5:10 PM" today, otherwise "Nov 2, 5:10 PM"
export function shortTime(sqliteTime) {
  const d = utcDate(sqliteTime);
  const time = d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  return d.toDateString() === new Date().toDateString()
    ? time
    : `${d.toLocaleDateString([], { month: "short", day: "numeric" })}, ${time}`;
}

// (2026, 10) -> "2026-11"   (month is 0-based, like JavaScript's Date)
export function monthKey(year, month) {
  return `${year}-${String(month + 1).padStart(2, "0")}`;
}
