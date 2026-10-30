import { env } from "cloudflare:workers";
import type { ChatGPTUser } from "@/app/chatgpt-auth";

/**
 * Admin authorization for CJ Online.
 *
 * Two layers, both required:
 *  1. The signed-in ChatGPT user must be on `CJ_ADMIN_ALLOWLIST`
 *     (comma-separated user IDs or emails, case-insensitive).
 *  2. The request must carry the correct shared admin code in the
 *     `x-cj-admin-code` header, compared against the `CJ_ADMIN_CODE`
 *     Cloudflare secret with a constant-time comparison.
 *
 * Failed code attempts are rate limited per user+IP (5 per 15 minutes).
 * There is no fallback or demo code: if the secret is not configured,
 * admin mutations are denied.
 */

const ALLOWLIST: string[] = String(env.CJ_ADMIN_ALLOWLIST ?? "")
  .split(",")
  .map((entry) => entry.trim().toLowerCase())
  .filter(Boolean);

export function isAllowedAdminUser(user: ChatGPTUser | null): boolean {
  if (!user || ALLOWLIST.length === 0) return false;
  const identities = [user.userId, user.email].filter(Boolean).map((value) => value.toLowerCase());
  return identities.some((identity) => ALLOWLIST.includes(identity));
}

/** Constant-time string comparison that does not depend on node:crypto. */
function safeEqual(left: string, right: string): boolean {
  const length = Math.max(left.length, right.length);
  let diff = left.length ^ right.length;
  for (let index = 0; index < length; index += 1) {
    diff |= (left.charCodeAt(index) || 0) ^ (right.charCodeAt(index) || 0);
  }
  return diff === 0;
}

const MAX_ATTEMPTS = 5;
const WINDOW_MS = 15 * 60 * 1000;
const MAX_TRACKED_KEYS = 1000;

/**
 * In-memory per-isolate rate limiting. Workers isolates are ephemeral, so
 * this is a best-effort backstop, not a durable limiter; production should
 * add Workers Rate Limiting bindings for stronger guarantees.
 */
const failures = new Map<string, { count: number; resetAt: number }>();

function attemptKey(user: ChatGPTUser, request: Request): string {
  const ip = request.headers.get("cf-connecting-ip") ?? "unknown";
  return `${user.userId}:${ip}`;
}

function recordFailure(key: string): void {
  const now = Date.now();
  const entry = failures.get(key);
  if (!entry || entry.resetAt <= now) {
    failures.set(key, { count: 1, resetAt: now + WINDOW_MS });
  } else {
    entry.count += 1;
  }
  if (failures.size > MAX_TRACKED_KEYS) {
    const cutoff = now;
    for (const [storedKey, stored] of failures) {
      if (stored.resetAt <= cutoff) failures.delete(storedKey);
    }
  }
}

function isBlocked(key: string): boolean {
  const entry = failures.get(key);
  return Boolean(entry && entry.resetAt > Date.now() && entry.count >= MAX_ATTEMPTS);
}

function clearFailures(key: string): void {
  failures.delete(key);
}

export type AdminGate =
  | { ok: true }
  | { ok: false; status: 401 | 429; message: string };

export function adminGate(request: Request, user: ChatGPTUser | null): AdminGate {
  if (!isAllowedAdminUser(user)) {
    return { ok: false, status: 401, message: "管理员权限不足" };
  }
  const provided = request.headers.get("x-cj-admin-code") ?? "";
  const configured = String(env.CJ_ADMIN_CODE ?? "").trim();
  if (!configured || !provided) {
    return { ok: false, status: 401, message: "管理员口令不正确" };
  }
  const key = attemptKey(user!, request);
  if (isBlocked(key)) {
    return { ok: false, status: 429, message: "尝试次数过多，请稍后再试" };
  }
  if (!safeEqual(provided, configured)) {
    recordFailure(key);
    return { ok: false, status: 401, message: "管理员口令不正确" };
  }
  clearFailures(key);
  return { ok: true };
}
