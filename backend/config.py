import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_BACKEND_DIR = Path(__file__).resolve().parent
_ROOT_DIR = _BACKEND_DIR.parent


@dataclass(frozen=True)
class Settings:
    database_url: str
    core_database_url: str
    session_secret: str
    frontend_origin: str
    admin_email: str
    mail_backend: str
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    smtp_from: str
    dashscope_api_key: str
    cj_journal_base_url: str
    cj_journal_api_key: str
    deepseek_api_key: str
    deepseek_model: str
    news_feed_urls: str
    session_ttl_hours: int
    cookie_secure: bool | None


def _load_env_file(path: Path) -> None:
    try:
        load_dotenv(path)
    except OSError:
        pass


def load_settings() -> Settings:
    _load_env_file(_ROOT_DIR / ".env")
    _load_env_file(_BACKEND_DIR / ".env")

    session_secret = (os.environ.get("SESSION_SECRET") or "").strip()
    if not session_secret:
        raise RuntimeError("SESSION_SECRET is required")
    _forbidden_secrets = {
        "dev-only-change-me",
        "change-me",
        "changeme",
        "change_me",
        "dev-secret",
        "devsecret",
        "replace-me",
        "placeholder",
    }
    if session_secret.lower() in _forbidden_secrets:
        raise RuntimeError(
            "SESSION_SECRET is a known placeholder and must not be used. "
            "Generate a unique value, e.g.: "
            "python3 -c \"import secrets; print(secrets.token_hex(32))\""
        )

    database_url = (os.environ.get("DATABASE_URL") or "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")

    # Two databases: content (DATABASE_URL) and core/CJ (CORE_DATABASE_URL).
    # When CORE_DATABASE_URL is unset it falls back to DATABASE_URL. Matching
    # URLs share one connection per request so a single SQLite file is not
    # written by two connections at once.
    core_database_url = (os.environ.get("CORE_DATABASE_URL") or "").strip() or database_url

    frontend_origin = (os.environ.get("FRONTEND_ORIGIN") or "http://localhost:5173").strip()
    admin_email = (os.environ.get("ADMIN_EMAIL") or "").strip().lower()
    mail_backend = (os.environ.get("MAIL_BACKEND") or "smtp").strip().lower()
    if mail_backend not in ("smtp", "console"):
        mail_backend = "smtp"
    smtp_port_raw = (os.environ.get("SMTP_PORT") or "587").strip()
    try:
        smtp_port = int(smtp_port_raw)
    except ValueError:
        smtp_port = 587
    smtp_user = (os.environ.get("SMTP_USER") or "").strip()
    smtp_from = (os.environ.get("SMTP_FROM") or smtp_user).strip()

    session_ttl_raw = (os.environ.get("SESSION_TTL_HOURS") or "720").strip()
    try:
        session_ttl_hours = int(session_ttl_raw)
    except ValueError:
        session_ttl_hours = 720
    if session_ttl_hours < 1:
        session_ttl_hours = 720

    cookie_secure_raw = (os.environ.get("COOKIE_SECURE") or "").strip().lower()
    cookie_secure: bool | None = None
    if cookie_secure_raw in ("true", "1", "yes", "on"):
        cookie_secure = True
    elif cookie_secure_raw in ("false", "0", "no", "off"):
        cookie_secure = False

    return Settings(
        database_url=database_url,
        core_database_url=core_database_url,
        session_secret=session_secret,
        frontend_origin=frontend_origin,
        admin_email=admin_email,
        mail_backend=mail_backend,
        smtp_host=(os.environ.get("SMTP_HOST") or "").strip(),
        smtp_port=smtp_port,
        smtp_user=smtp_user,
        smtp_password=os.environ.get("SMTP_PASSWORD") or "",
        smtp_from=smtp_from,
        dashscope_api_key=(os.environ.get("DASHSCOPE_API_KEY") or "").strip(),
        cj_journal_base_url=(os.environ.get("CJ_JOURNAL_BASE_URL") or "").strip().rstrip("/"),
        cj_journal_api_key=(os.environ.get("CJ_JOURNAL_API_KEY") or "").strip(),
        deepseek_api_key=(os.environ.get("DEEPSEEK_API_KEY") or "").strip(),
        deepseek_model=(os.environ.get("DEEPSEEK_MODEL") or "deepseek-chat").strip() or "deepseek-chat",
        news_feed_urls=(os.environ.get("NEWS_FEED_URLS") or "").strip(),
        session_ttl_hours=session_ttl_hours,
        cookie_secure=cookie_secure,
    )
