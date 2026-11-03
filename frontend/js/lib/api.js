// Talking to the server. Every request goes through api(), which sends/receives JSON
// and sends you to the login page if your session has expired.

export async function api(method, path, body) {
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
