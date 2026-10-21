import hashlib
import hmac
import secrets

COOKIE_NAME = "scoop_session"
_PBKDF2_ITERATIONS = 600_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        _PBKDF2_ITERATIONS,
    )
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt}${dk.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        scheme, iterations, salt, digest = password_hash.split("$", 3)
    except ValueError:
        return False
    if scheme != "pbkdf2_sha256":
        return False
    try:
        rounds = int(iterations)
    except ValueError:
        return False
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        rounds,
    )
    return hmac.compare_digest(dk.hex(), digest)


def needs_rehash(password_hash: str) -> bool:
    """True when a stored hash uses an older scheme or fewer iterations."""
    try:
        scheme, iterations, _salt, _digest = password_hash.split("$", 3)
    except (AttributeError, ValueError):
        return True
    if scheme != "pbkdf2_sha256":
        return True
    try:
        rounds = int(iterations)
    except ValueError:
        return True
    return rounds < _PBKDF2_ITERATIONS


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def sign_cookie_value(token: str, secret: str) -> str:
    sig = hmac.new(secret.encode("utf-8"), token.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{token}.{sig}"


def unsign_cookie_value(value: str, secret: str) -> str | None:
    if "." not in value:
        return None
    token, sig = value.rsplit(".", 1)
    expected = hmac.new(secret.encode("utf-8"), token.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return None
    return token
