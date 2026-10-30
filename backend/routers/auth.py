from uuid import uuid4
import logging

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from avatars import (
    ALLOWED_TYPES,
    MAX_AVATAR_BYTES,
    DEFAULT_AVATAR,
    ensure_avatar_dir,
    normalize_avatar,
    preset_avatar,
)
from deps import get_core_db, get_current_user, get_db
from errors import ApiError, StorageError, unauthenticated, validation_error
from models import User, to_iso, utc_now
from mail import send_verification_email
from schemas import (
    AVATAR_PRESETS,
    ChangePasswordBody,
    EmailCodeBody,
    ForumActivity,
    LoginBody,
    Notice,
    NoticeList,
    PasswordResetBody,
    RegisterBody,
    SetAvatarPresetBody,
    UserPrivate,
)
from security import COOKIE_NAME, hash_password, needs_rehash, sign_cookie_value, unsign_cookie_value, verify_password
from store import (
    apply_admin_email,
    consume_email_code,
    create_session,
    get_active_session,
    forum_activity_unread,
    get_user_by_email,
    issue_email_code,
    list_system_notices,
    mark_forum_activity_read,
)
from identity import dump_roles, primary_role, user_roles
from ratelimit import email_code_limiter
from validate import (
    change_password_field_errors,
    email_code_field_errors,
    login_field_errors,
    normalize_email,
    password_reset_field_errors,
    register_field_errors,
)

router = APIRouter()


def _user_private(user: User) -> dict:
    return UserPrivate(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        roles=user_roles(user),
        avatar=normalize_avatar(user.avatar),
        muted=bool(user.muted),
        terms_accepted_at=to_iso(user.terms_accepted_at) if user.terms_accepted_at else None,
        created_at=to_iso(user.created_at),
    ).model_dump()


def _cookie_secure(settings) -> bool:
    """Explicit COOKIE_SECURE wins; otherwise fall back to the origin scheme.

    The fallback exists for local setups (http://localhost). When it produces
    an insecure cookie, say so in the logs instead of failing silently.
    """
    if settings.cookie_secure is not None:
        return settings.cookie_secure
    auto = settings.frontend_origin.startswith("https://")
    if not auto:
        logging.getLogger("elegram.cj").warning(
            "COOKIE_SECURE is not set and FRONTEND_ORIGIN is not https:// — "
            "session cookies will not carry the Secure flag. Set COOKIE_SECURE=true "
            "in production."
        )
    return auto


def _set_session_cookie(response: Response, token: str, secret: str, settings) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=sign_cookie_value(token, secret),
        httponly=True,
        samesite="lax",
        secure=_cookie_secure(settings),
        path="/",
    )


def _clear_session_cookie(response: Response, settings) -> None:
    response.delete_cookie(key=COOKIE_NAME, path="/", samesite="lax", secure=_cookie_secure(settings))


@router.post("/auth/email-codes", status_code=204)
def request_email_code(body: EmailCodeBody, request: Request, db: Session = Depends(get_core_db)) -> None:
    fields = email_code_field_errors(body.email, body.purpose)
    if fields:
        raise validation_error(fields)

    email = normalize_email(body.email)
    purpose = body.purpose

    # Bound code requests per client IP and per mailbox so one client cannot
    # enumerate the school directory or flood the mail server.
    client_ip = request.client.host if request.client else "unknown"
    if email_code_limiter.hit(f"ip:{client_ip}") or email_code_limiter.hit(f"mail:{email}"):
        raise ApiError(
            429,
            "too_many_requests",
            "Too many code requests. Try again later.",
        )

    try:
        user = get_user_by_email(db, email)
        if purpose == "register":
            # Never reveal whether the account exists: send a code only when
            # registration could actually succeed, and answer 204 either way
            # (the reset flow below already behaves like this).
            if user is None:
                code = issue_email_code(db, email, purpose)
                send_verification_email(request.app.state.settings, email, code, purpose)
            return
        if user is not None:
            code = issue_email_code(db, email, purpose)
            send_verification_email(request.app.state.settings, email, code, purpose)
    except ApiError:
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise StorageError() from exc


@router.post("/auth/register")
def register(body: RegisterBody, request: Request, db: Session = Depends(get_core_db)):
    fields = register_field_errors(
        body.email, body.password, body.display_name, body.code, body.accept_terms
    )
    if fields:
        raise validation_error(fields)

    email = normalize_email(body.email)
    # PBKDF2 is the dominant cost here; run it before the account lookup so
    # the response time does not reveal whether the email is registered.
    password_hash = hash_password(body.password)
    consume_email_code(db, email, "register", body.code)
    if get_user_by_email(db, email) is not None:
        raise ApiError(
            409,
            "email_taken",
            "An account with this email already exists.",
            [{"field": "email", "message": "This email is already registered."}],
        )

    admin_email = request.app.state.settings.admin_email
    roles = ["student"]
    if admin_email and email == admin_email:
        roles.append("super_admin")
    user = User(
        id=str(uuid4()),
        email=email,
        password_hash=password_hash,
        display_name=body.display_name.strip(),
        role=primary_role(roles),
        roles=dump_roles(roles),
        muted=False,
        avatar=DEFAULT_AVATAR,
        terms_accepted_at=utc_now(),
        created_at=utc_now(),
    )
    try:
        db.add(user)
        db.flush()
        token = create_session(db, user.id, request.app.state.settings.session_ttl_hours)
    except IntegrityError as exc:
        db.rollback()
        detail = str(getattr(exc, "orig", None) or exc)
        if "users.email" in detail:
            raise ApiError(
                409,
                "email_taken",
                "An account with this email already exists.",
                [{"field": "email", "message": "This email is already registered."}],
            ) from exc
        raise StorageError() from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise StorageError() from exc

    response = JSONResponse(status_code=201, content=_user_private(user))
    _set_session_cookie(response, token, request.app.state.settings.session_secret, request.app.state.settings)
    return response


@router.post("/auth/password-reset", status_code=204)
def reset_password(body: PasswordResetBody, db: Session = Depends(get_core_db)) -> None:
    fields = password_reset_field_errors(body.email, body.code, body.password)
    if fields:
        raise validation_error(fields)

    email = normalize_email(body.email)
    consume_email_code(db, email, "reset", body.code)
    try:
        user = get_user_by_email(db, email)
        if user is None:
            raise validation_error(
                [{"field": "code", "message": "Enter the 6-digit code sent to your email."}]
            )
        user.password_hash = hash_password(body.password)
        db.flush()
    except ApiError:
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise StorageError() from exc


@router.post("/auth/login")
def login(body: LoginBody, request: Request, db: Session = Depends(get_core_db)):
    fields = login_field_errors(body.email, body.password)
    if fields:
        raise validation_error(fields)

    try:
        user = get_user_by_email(db, normalize_email(body.email))
    except SQLAlchemyError as exc:
        raise StorageError() from exc

    if user is None or not verify_password(body.password, user.password_hash):
        raise ApiError(401, "invalid_credentials", "Email or password is incorrect.")

    try:
        apply_admin_email(user, request.app.state.settings.admin_email)
        if needs_rehash(user.password_hash):
            user.password_hash = hash_password(body.password)
        token = create_session(db, user.id, request.app.state.settings.session_ttl_hours)
    except SQLAlchemyError as exc:
        db.rollback()
        raise StorageError() from exc

    response = JSONResponse(status_code=200, content=_user_private(user))
    _set_session_cookie(response, token, request.app.state.settings.session_secret, request.app.state.settings)
    return response


@router.post("/auth/logout", status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_core_db)) -> None:
    raw = request.cookies.get(COOKIE_NAME)
    if not raw:
        raise unauthenticated()
    token = unsign_cookie_value(raw, request.app.state.settings.session_secret)
    if not token:
        raise unauthenticated()
    record = get_active_session(db, token)
    if record is None:
        raise unauthenticated()
    record.revoked_at = utc_now()
    _clear_session_cookie(response, request.app.state.settings)


@router.get("/me")
def me(user: User = Depends(get_current_user)) -> dict:
    return _user_private(user)


@router.put("/me/password", status_code=204)
def change_password(
    body: ChangePasswordBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_core_db),
) -> None:
    fields = change_password_field_errors(body.current_password, body.password)
    if fields:
        raise validation_error(fields)
    if not verify_password(body.current_password, user.password_hash):
        raise validation_error(
            [{"field": "current_password", "message": "Current password is incorrect."}]
        )
    try:
        user.password_hash = hash_password(body.password)
        db.flush()
    except SQLAlchemyError as exc:
        db.rollback()
        raise StorageError() from exc


@router.put("/me/avatar")
def set_avatar_preset(
    body: SetAvatarPresetBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_core_db),
):
    if body.preset not in AVATAR_PRESETS:
        raise validation_error(
            [{"field": "preset", "message": "Must be one of: oak, gym, book, dorm, bus, night."}]
        )
    user.avatar = preset_avatar(body.preset)
    try:
        db.flush()
    except SQLAlchemyError as exc:
        raise StorageError() from exc
    return _user_private(user)


@router.get("/me/forum-activity")
def forum_activity(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return ForumActivity(unread=forum_activity_unread(db, user.id)).model_dump()


@router.post("/me/forum-activity/read", status_code=204)
def read_forum_activity(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> None:
    mark_forum_activity_read(db, user.id)


@router.get("/me/notices")
def my_notices(user: User = Depends(get_current_user), db: Session = Depends(get_core_db)):
    try:
        rows = list_system_notices(db, user.id)
    except SQLAlchemyError as exc:
        raise StorageError() from exc
    return NoticeList(
        items=[Notice(id=row.id, body=row.body, created_at=to_iso(row.created_at)) for row in rows]
    ).model_dump()


@router.post("/me/avatar")
async def upload_avatar(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_core_db),
    file: UploadFile = File(...),
):
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    ext = ALLOWED_TYPES.get(content_type)
    if ext is None:
        raise validation_error(
            [{"field": "file", "message": "Avatar must be a jpeg, png, or webp image."}]
        )
    data = await file.read()
    if not data or len(data) > MAX_AVATAR_BYTES:
        raise validation_error([{"field": "file", "message": "Avatar must be 1–1000000 bytes."}])
    try:
        folder = ensure_avatar_dir()
        path = folder / f"{user.id}.{ext}"
        path.write_bytes(data)
        user.avatar = f"/uploads/avatars/{user.id}.{ext}"
        db.flush()
    except OSError as exc:
        raise StorageError() from exc
    except SQLAlchemyError as exc:
        raise StorageError() from exc
    return _user_private(user)
