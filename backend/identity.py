import json

ROLE_ORDER = ("student", "teacher", "editor", "admin", "super_admin")
ASSIGNABLE_ROLES = ("student", "teacher", "editor", "admin")


def normalize_roles(roles) -> list[str]:
    found = {role for role in roles if role in ROLE_ORDER}
    return [name for name in ROLE_ORDER if name in found]


def dump_roles(roles) -> str:
    return json.dumps(normalize_roles(roles))


def load_roles(raw: str | None) -> list[str]:
    if not raw:
        return ["student"]
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return ["student"]
    if not isinstance(parsed, list):
        return ["student"]
    return normalize_roles(item for item in parsed if isinstance(item, str))


def user_roles(user) -> list[str]:
    return load_roles(getattr(user, "roles", None))


def user_has(user, *names: str) -> bool:
    owned = set(user_roles(user))
    return any(name in owned for name in names)


def primary_role(roles) -> str:
    ordered = set(normalize_roles(roles))
    for name in ("super_admin", "admin", "editor", "teacher", "student"):
        if name in ordered:
            return name
    return "student"


def assign_roles(user, roles) -> list[str]:
    ordered = normalize_roles(roles) or ["student"]
    user.roles = json.dumps(ordered)
    user.role = primary_role(ordered)
    return ordered
