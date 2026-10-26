export const CATEGORY_LABELS = {
  news: "NEWS",
  forum: "FORUM",
};

export const CATEGORY_ROUTES = [
  { to: "/forum", label: "FORUM", category: "forum" },
  { to: "/bell", label: "BELL", category: null },
  { to: "/bottles", label: "BOTTLES", category: null },
  { to: "/cj", label: "CJ", category: null },
  { to: "/opinion", label: "OPINION", category: null },
];

const FORUM_LISTS = new Set(["/forum", "/forum/latest", "/forum/all", "/forum/mine"]);

export function forumListPath(pathname) {
  return FORUM_LISTS.has(pathname) ? pathname : null;
}

export function hasRole(user, role) {
  return Array.isArray(user?.roles) && user.roles.includes(role);
}

export function canEditNews(user) {
  return hasRole(user, "editor") || hasRole(user, "super_admin");
}

const NEWS_TOPIC_LABELS = {
  sport: "Sports",
  dorm: "Dorm",
  scoop: "Scoop",
  school: "Scoop",
};

export function newsTopicLabel(topic) {
  return NEWS_TOPIC_LABELS[topic] || topic;
}

export function newsTopicsLabel(topics) {
  return (topics || []).map(newsTopicLabel).join(" · ");
}

export function canDeletePosts(user) {
  return hasRole(user, "admin") || hasRole(user, "super_admin");
}

export function canPinPosts(user) {
  return hasRole(user, "super_admin");
}

export function categoryLabel(category) {
  return CATEGORY_LABELS[category] || (category || "").toUpperCase();
}

function dateLocale(lang) {
  return lang === "zh" ? "zh-CN" : "en-US";
}

export function formatToday(lang = "en") {
  return new Date().toLocaleDateString(dateLocale(lang), {
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}

export function formatDateline(iso, lang = "en") {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString(dateLocale(lang), {
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}

export function formatRelative(iso, lang = "en") {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const zh = lang === "zh";
  const minutes = Math.max(0, Math.floor((Date.now() - then) / 60000));
  if (minutes < 1) return zh ? "刚刚" : "just now";
  if (minutes < 60) return zh ? `${minutes} 分钟前` : `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return zh ? `${hours} 小时前` : `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return zh ? `${days} 天前` : `${days}d ago`;
  return formatDateline(iso, lang);
}
