const PRESETS = new Set(["oak", "gym", "book", "dorm", "bus", "night"]);

function apiOrigin() {
  const base = import.meta.env.VITE_API_BASE || "/api/v1";
  if (base.startsWith("http://") || base.startsWith("https://")) {
    return new URL(base).origin;
  }
  return "";
}

export function avatarSrc(avatar) {
  if (typeof avatar === "string" && avatar.startsWith("preset:")) {
    const preset = avatar.slice("preset:".length);
    if (PRESETS.has(preset)) return `/avatars/${preset}.svg`;
  }
  if (typeof avatar === "string" && avatar.startsWith("/uploads/avatars/")) {
    return `${apiOrigin()}${avatar}`;
  }
  return "/avatars/oak.svg";
}

export function uploadSrc(path) {
  if (typeof path === "string" && path.startsWith("/uploads/")) {
    return `${apiOrigin()}${path}`;
  }
  return "";
}
