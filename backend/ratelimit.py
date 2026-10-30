"""Small in-process rate limiter for sensitive endpoints.

This is deliberately dependency-free: it guards against single-process abuse
(before a reverse proxy or a production rate-limit layer). State lives in
memory and is reset on restart, which is fine for the endpoints it protects.
"""

import os
import threading
import time

_MAX_KEYS = 10_000


def _env_int(name: str, default: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(1, value)


class SlidingWindowLimiter:
    """Fixed-window limiter keyed by arbitrary strings (IPs, mailboxes, ...)."""

    def __init__(self, limit: int, window_seconds: float) -> None:
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def hit(self, key: str) -> bool:
        """Record an attempt for `key`; True when the key is over the limit."""
        limit = self.limit
        if getattr(self, "env_limit", None) is not None:
            limit = self.env_limit()
        now = time.monotonic()
        with self._lock:
            recent = [stamp for stamp in self._hits.get(key, []) if now - stamp < self.window]
            recent.append(now)
            self._hits[key] = recent
            if len(self._hits) > _MAX_KEYS:
                cutoff = now - self.window
                keep = {}
                for stored_key, stamps in self._hits.items():
                    fresh = [stamp for stamp in stamps if stamp >= cutoff]
                    if fresh:
                        keep[stored_key] = fresh
                self._hits = keep
            return len(recent) > limit

    def reset(self) -> None:
        """Drop all recorded hits (used by tests)."""
        with self._lock:
            self._hits.clear()


# Verification codes: 6 requests per key (IP or mailbox) per hour. Combined
# with the existing per-email 60s resend delay this bounds both enumeration
# and mail-server load. The limit is re-read from the environment on every hit
# so operators (and tests) can adjust it without a restart.
email_code_limiter = SlidingWindowLimiter(
    limit=_env_int("EMAIL_CODE_PER_KEY_PER_HOUR", 6),
    window_seconds=3600,
)
email_code_limiter.env_limit = lambda: _env_int("EMAIL_CODE_PER_KEY_PER_HOUR", 6)
