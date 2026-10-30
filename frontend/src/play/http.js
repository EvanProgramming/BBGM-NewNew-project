function apiOrigin() {
  const base = import.meta.env.VITE_API_BASE || "/api/v1";
  if (base.startsWith("http")) return base.replace(/\/api\/v1\/?$/, "");
  return window.location.origin;
}

export function gamesUrl(path) {
  return `${apiOrigin()}/api/v1/games${path}`;
}

export async function postJson(path, body) {
  const response = await fetch(gamesUrl(path), {
    method: "POST",
    credentials: "include",
    headers:
      body === undefined
        ? { Accept: "application/json" }
        : { Accept: "application/json", "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  return await response.json();
}

export function roomSocketUrl(game, code) {
  const origin = apiOrigin();
  const httpBase = origin.endsWith("/") ? origin : `${origin}/`;
  const ws = new URL(
    `api/v1/games/${game}/rooms/${encodeURIComponent(code)}/ws`,
    httpBase,
  );
  ws.protocol = ws.protocol === "https:" ? "wss:" : "ws:";
  return ws.toString();
}
