import re
from uuid import UUID

from errors import ApiError, validation_error
from schemas import CATEGORIES, CATEGORY_MESSAGE

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
CODE_RE = re.compile(r"^\d{6}$")
SCHOOL_EMAIL_SUFFIX = "@basischina.com"
SCHOOL_EMAIL_MESSAGE = "Use an email ending in @basischina.com."
CODE_MESSAGE = "Enter the 6-digit code sent to your email."
EMAIL_CODE_PURPOSES = ("register", "reset")
PURPOSE_MESSAGE = "Must be one of: register, reset."


def parse_page(value: str | None) -> int:
    if value is None or value == "":
        return 1
    if not value.isdigit() or int(value) < 1:
        raise ApiError(400, "bad_request", "page must be an integer greater than or equal to 1.")
    return int(value)


def parse_page_size(value: str | None) -> int:
    if value is None or value == "":
        return 20
    if not value.isdigit():
        raise ApiError(400, "bad_request", "page_size must be an integer between 1 and 50.")
    size = int(value)
    if size < 1 or size > 50:
        raise ApiError(400, "bad_request", "page_size must be an integer between 1 and 50.")
    return size


def parse_optional_category(value: str | None) -> str | None:
    if value is None:
        return None
    if value not in CATEGORIES:
        raise validation_error([{"field": "category", "message": CATEGORY_MESSAGE}])
    return value


FORUM_FEEDS = ("recommended", "latest", "all", "mine")
FEED_MESSAGE = "Must be one of: recommended, latest, all, mine."


def parse_forum_feed(value: str | None, category: str | None) -> str | None:
    if value is None or value == "":
        return "recommended" if category == "forum" else None
    if category != "forum":
        raise validation_error([{"field": "feed", "message": "feed applies only to forum."}])
    if value not in FORUM_FEEDS:
        raise validation_error([{"field": "feed", "message": FEED_MESSAGE}])
    return value


def parse_uuid(value: str, field: str = "post_id") -> str:
    try:
        return str(UUID(value))
    except ValueError as exc:
        raise ApiError(400, "bad_request", f"{field} must be a UUID.") from exc


def normalize_email(value: str) -> str:
    return value.strip().lower()


def normalize_code(value: str) -> str:
    return "".join(ch for ch in (value or "") if ch.isdigit())


def email_field_error(email: str, *, required: bool = True) -> dict[str, str] | None:
    raw = email.strip()
    if not raw:
        if required:
            return {"field": "email", "message": "Email is required."}
        return {"field": "email", "message": "Enter a valid email address."}
    normalized = normalize_email(email)
    if not EMAIL_RE.match(normalized):
        return {"field": "email", "message": "Enter a valid email address."}
    if not normalized.endswith(SCHOOL_EMAIL_SUFFIX):
        return {"field": "email", "message": SCHOOL_EMAIL_MESSAGE}
    return None


def code_field_error(code: str) -> dict[str, str] | None:
    if not CODE_RE.match(normalize_code(code)):
        return {"field": "code", "message": CODE_MESSAGE}
    return None


def register_field_errors(
    email: str, password: str, display_name: str, code: str, accept_terms: bool
) -> list[dict[str, str]]:
    fields: list[dict[str, str]] = []
    email_error = email_field_error(email)
    if email_error:
        fields.append(email_error)
    if len(password) < 8 or len(password) > 128:
        fields.append({"field": "password", "message": "Password must be 8–128 characters."})
    name = display_name.strip()
    if not name or len(name) > 40:
        fields.append({"field": "display_name", "message": "Display name must be 1–40 characters."})
    code_error = code_field_error(code)
    if code_error:
        fields.append(code_error)
    if accept_terms is not True:
        fields.append({"field": "accept_terms", "message": "You must accept the user agreement."})
    return fields


def login_field_errors(email: str, password: str) -> list[dict[str, str]]:
    fields: list[dict[str, str]] = []
    email_error = email_field_error(email)
    if email_error:
        fields.append(email_error)
    if not password:
        fields.append({"field": "password", "message": "Password is required."})
    return fields


def email_code_field_errors(email: str, purpose: str) -> list[dict[str, str]]:
    fields: list[dict[str, str]] = []
    email_error = email_field_error(email)
    if email_error:
        fields.append(email_error)
    if purpose not in EMAIL_CODE_PURPOSES:
        fields.append({"field": "purpose", "message": PURPOSE_MESSAGE})
    return fields


def change_password_field_errors(current_password: str, password: str) -> list[dict[str, str]]:
    fields: list[dict[str, str]] = []
    if not current_password:
        fields.append({"field": "current_password", "message": "Current password is required."})
    if len(password) < 8 or len(password) > 128:
        fields.append({"field": "password", "message": "Password must be 8–128 characters."})
    elif current_password and password == current_password:
        fields.append({"field": "password", "message": "Choose a different password."})
    return fields


def password_reset_field_errors(email: str, code: str, password: str) -> list[dict[str, str]]:
    fields: list[dict[str, str]] = []
    email_error = email_field_error(email)
    if email_error:
        fields.append(email_error)
    code_error = code_field_error(code)
    if code_error:
        fields.append(code_error)
    if len(password) < 8 or len(password) > 128:
        fields.append({"field": "password", "message": "Password must be 8–128 characters."})
    return fields
