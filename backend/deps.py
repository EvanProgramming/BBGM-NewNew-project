from typing import Iterator

from fastapi import Depends, Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from errors import StorageError, account_muted, forbidden, unauthenticated
from models import User
from schemas import CJ_EDITOR_ROLES, CJ_VIEWER_ROLES, MODERATOR_ROLES, NEWSROOM_ROLES
from security import COOKIE_NAME, unsign_cookie_value
from store import get_session_by_token


def _session_scope(factory) -> Iterator[Session]:
    session = factory()
    try:
        yield session
        session.commit()
    except StorageError:
        session.rollback()
        raise
    except SQLAlchemyError as exc:
        session.rollback()
        raise StorageError() from exc
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db(request: Request):
    """Content database session (posts, news blocks, comments, likes, audit)."""
    yield from _session_scope(request.app.state.content_session_factory)


def get_core_db(request: Request):
    """CJ student database session (users, sessions, CJ schedule, Teams)."""
    yield from _session_scope(request.app.state.core_session_factory)


def get_current_user(request: Request, db: Session = Depends(get_core_db)) -> User:
    raw = request.cookies.get(COOKIE_NAME)
    if not raw:
        raise unauthenticated()
    token = unsign_cookie_value(raw, request.app.state.settings.session_secret)
    if not token:
        raise unauthenticated()
    record = get_session_by_token(db, token)
    if record is None or record.revoked_at is not None:
        raise unauthenticated()
    return record.user


def require_not_muted(user: User) -> None:
    if user.muted:
        raise account_muted()


def get_optional_user(request: Request, db: Session = Depends(get_core_db)) -> User | None:
    raw = request.cookies.get(COOKIE_NAME)
    if not raw:
        return None
    token = unsign_cookie_value(raw, request.app.state.settings.session_secret)
    if not token:
        return None
    record = get_session_by_token(db, token)
    if record is None or record.revoked_at is not None:
        return None
    return record.user


def get_super_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "super_admin":
        raise forbidden()
    return user


def get_moderator(user: User = Depends(get_current_user)) -> User:
    if user.role not in MODERATOR_ROLES:
        raise forbidden()
    return user


def get_newsroom_user(user: User = Depends(get_current_user)) -> User:
    if user.role not in NEWSROOM_ROLES:
        raise forbidden()
    return user


def get_cj_viewer(user: User = Depends(get_current_user)) -> User:
    if user.role not in CJ_VIEWER_ROLES:
        raise forbidden()
    return user


def get_cj_editor(user: User = Depends(get_current_user)) -> User:
    if user.role not in CJ_EDITOR_ROLES:
        raise forbidden()
    return user
