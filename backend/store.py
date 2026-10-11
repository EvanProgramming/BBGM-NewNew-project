from typing import Iterable
from uuid import uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from errors import StorageError
from datetime import timedelta, timezone

from models import (
    AuditEvent,
    Comment,
    EmailCode,
    NewsBlock,
    Post,
    PostLike,
    SessionRecord,
    CJTeacherSubject,
    SystemNotice,
    User,
    utc_now,
)
from security import hash_token, new_session_token, verify_password, hash_password


def make_excerpt(body: str) -> str:
    text = body.strip()
    return text[:160]


# ---------------------------------------------------------------------------
# Core (CJ student) session helpers
# ---------------------------------------------------------------------------


def create_session(db: Session, user_id: str) -> str:
    token = new_session_token()
    record = SessionRecord(
        id=str(uuid4()),
        token_hash=hash_token(token),
        user_id=user_id,
        revoked_at=None,
        created_at=utc_now(),
    )
    db.add(record)
    db.flush()
    return token


def get_active_session(db: Session, token: str) -> SessionRecord | None:
    return db.scalar(
        select(SessionRecord).where(
            SessionRecord.token_hash == hash_token(token),
            SessionRecord.revoked_at.is_(None),
        )
    )


def get_session_by_token(db: Session, token: str) -> SessionRecord | None:
    return db.scalar(
        select(SessionRecord).where(SessionRecord.token_hash == hash_token(token))
    )


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email))


def users_by_ids(db: Session, ids: Iterable[str]) -> dict[str, User]:
    """Load users (from the core database) for the given ids."""
    unique = {value for value in ids if value}
    if not unique:
        return {}
    try:
        rows = db.scalars(select(User).where(User.id.in_(unique))).all()
    except SQLAlchemyError as exc:
        raise StorageError() from exc
    return {row.id: row for row in rows}


def apply_admin_email(user: User, admin_email: str) -> None:
    if admin_email and user.email == admin_email and user.role != "super_admin":
        user.role = "super_admin"


def add_system_notice(db: Session, *, user_id: str, body: str) -> None:
    db.add(
        SystemNotice(
            id=str(uuid4()),
            user_id=user_id,
            body=body,
            created_at=utc_now(),
        )
    )
    db.flush()


def list_system_notices(db: Session, user_id: str) -> list[SystemNotice]:
    return list(
        db.scalars(
            select(SystemNotice)
            .where(SystemNotice.user_id == user_id)
            .order_by(SystemNotice.created_at.desc())
        ).all()
    )


def revoke_user_sessions(db: Session, user_id: str) -> None:
    now = utc_now()
    rows = db.scalars(
        select(SessionRecord).where(
            SessionRecord.user_id == user_id,
            SessionRecord.revoked_at.is_(None),
        )
    ).all()
    for row in rows:
        row.revoked_at = now


CODE_TTL_MINUTES = 2
CODE_RESEND_SECONDS = 60
CODE_MAX_ATTEMPTS = 5


def _as_utc(dt):
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def issue_email_code(db: Session, email: str, purpose: str) -> str:
    now = utc_now()
    latest = db.scalar(
        select(EmailCode)
        .where(EmailCode.email == email, EmailCode.purpose == purpose)
        .order_by(EmailCode.created_at.desc())
    )
    if latest is not None:
        elapsed = (_as_utc(now) - _as_utc(latest.created_at)).total_seconds()
        if elapsed < CODE_RESEND_SECONDS:
            from errors import validation_error

            raise validation_error([{"field": "email", "message": "Please wait before requesting another code."}])
        db.execute(delete(EmailCode).where(EmailCode.email == email, EmailCode.purpose == purpose))

    from secrets import randbelow

    code = f"{randbelow(1_000_000):06d}"
    record = EmailCode(
        id=str(uuid4()),
        email=email,
        purpose=purpose,
        code_hash=hash_password(code),
        expires_at=now + timedelta(minutes=CODE_TTL_MINUTES),
        attempt_count=0,
        created_at=now,
    )
    db.add(record)
    db.commit()
    return code


def consume_email_code(db: Session, email: str, purpose: str, code: str) -> bool:
    from errors import validation_error
    from validate import normalize_code

    now = _as_utc(utc_now())
    latest = db.scalar(
        select(EmailCode)
        .where(EmailCode.email == email, EmailCode.purpose == purpose)
        .order_by(EmailCode.created_at.desc())
    )
    invalid = [{"field": "code", "message": "Enter the 6-digit code sent to your email."}]
    if latest is None or _as_utc(latest.expires_at) <= now or latest.attempt_count >= CODE_MAX_ATTEMPTS:
        raise validation_error(invalid)
    if not verify_password(normalize_code(code), latest.code_hash):
        latest.attempt_count += 1
        db.flush()
        raise validation_error(invalid)
    db.delete(latest)
    db.flush()
    return True


def delete_user_account(core: Session, content: Session, user: User) -> list[str]:
    """Delete a user from the core DB and all of their content from the content DB."""
    user_id = user.id
    post_ids = list(content.scalars(select(Post.id).where(Post.author_id == user_id)).all())
    try:
        core.execute(delete(SystemNotice).where(SystemNotice.user_id == user_id))
        for post in content.scalars(select(Post).where(Post.author_id == user_id)).all():
            delete_post_graph(content, post)
        content.execute(delete(Comment).where(Comment.author_id == user_id, Comment.parent_id.is_not(None)))
        floor_ids = list(
            content.scalars(
                select(Comment.id).where(Comment.author_id == user_id, Comment.parent_id.is_(None))
            ).all()
        )
        if floor_ids:
            content.execute(delete(Comment).where(Comment.parent_id.in_(floor_ids)))
            content.execute(delete(Comment).where(Comment.id.in_(floor_ids)))
        content.execute(delete(PostLike).where(PostLike.user_id == user_id))
        content.execute(delete(AuditEvent).where(AuditEvent.actor_id == user_id))
        core.execute(delete(CJTeacherSubject).where(CJTeacherSubject.user_id == user_id))
        core.execute(delete(SessionRecord).where(SessionRecord.user_id == user_id))
        core.delete(user)
        content.flush()
        core.flush()
    except SQLAlchemyError as exc:
        raise StorageError() from exc
    return post_ids


# ---------------------------------------------------------------------------
# Content (news & sharing) helpers
# ---------------------------------------------------------------------------


def create_post_with_audit(
    db: Session,
    *,
    author_id: str,
    title: str,
    body: str,
    category: str,
) -> Post:
    now = utc_now()
    post = Post(
        id=str(uuid4()),
        author_id=author_id,
        title=title,
        body=body,
        excerpt=make_excerpt(body),
        category=category,
        is_activity=False,
        starts_at=None,
        location=None,
        status="published",
        images="[]",
        created_at=now,
        updated_at=now,
    )
    audit = AuditEvent(
        id=str(uuid4()),
        actor_id=author_id,
        action="create_post",
        post_id=post.id,
        at=now,
    )
    try:
        db.add(post)
        db.flush()
        db.add(audit)
        db.flush()
    except SQLAlchemyError as exc:
        db.rollback()
        raise StorageError("Could not save the post. Try again in a moment.") from exc
    return post


def create_comment(
    db: Session,
    *,
    post_id: str,
    author_id: str,
    body: str,
    parent_id: str | None,
) -> Comment:
    comment = Comment(
        id=str(uuid4()),
        post_id=post_id,
        author_id=author_id,
        parent_id=parent_id,
        body=body,
        created_at=utc_now(),
    )
    try:
        db.add(comment)
        db.flush()
    except SQLAlchemyError as exc:
        db.rollback()
        raise StorageError() from exc
    return comment


def count_likes(db: Session, post_id: str) -> int:
    try:
        return db.scalar(select(func.count()).select_from(PostLike).where(PostLike.post_id == post_id)) or 0
    except SQLAlchemyError as exc:
        raise StorageError() from exc


def user_liked(db: Session, *, user_id: str, post_id: str) -> bool:
    try:
        return (
            db.scalar(select(PostLike.id).where(PostLike.user_id == user_id, PostLike.post_id == post_id))
            is not None
        )
    except SQLAlchemyError as exc:
        raise StorageError() from exc


def like_counts_for_posts(db: Session, post_ids: list[str]) -> dict[str, int]:
    if not post_ids:
        return {}
    try:
        rows = db.execute(
            select(PostLike.post_id, func.count())
            .where(PostLike.post_id.in_(post_ids))
            .group_by(PostLike.post_id)
        ).all()
    except SQLAlchemyError as exc:
        raise StorageError() from exc
    return {post_id: count for post_id, count in rows}


def liked_post_ids(db: Session, *, user_id: str, post_ids: list[str]) -> set[str]:
    if not post_ids:
        return set()
    try:
        return set(
            db.scalars(
                select(PostLike.post_id).where(PostLike.user_id == user_id, PostLike.post_id.in_(post_ids))
            ).all()
        )
    except SQLAlchemyError as exc:
        raise StorageError() from exc


def add_like(db: Session, *, user_id: str, post_id: str) -> bool:
    if user_liked(db, user_id=user_id, post_id=post_id):
        return False
    like = PostLike(
        id=str(uuid4()),
        user_id=user_id,
        post_id=post_id,
        created_at=utc_now(),
    )
    try:
        with db.begin_nested():
            db.add(like)
            db.flush()
        return True
    except IntegrityError:
        return False
    except SQLAlchemyError as exc:
        raise StorageError() from exc


def remove_like(db: Session, *, user_id: str, post_id: str) -> None:
    try:
        like = db.scalar(select(PostLike).where(PostLike.user_id == user_id, PostLike.post_id == post_id))
        if like is not None:
            db.delete(like)
            db.flush()
    except SQLAlchemyError as exc:
        raise StorageError() from exc


def create_news_draft(db: Session, *, author_id: str, title: str) -> Post:
    now = utc_now()
    post = Post(
        id=str(uuid4()),
        author_id=author_id,
        title=title,
        body="",
        excerpt="",
        category="news",
        is_activity=False,
        starts_at=None,
        location=None,
        status="draft",
        images="[]",
        created_at=now,
        updated_at=now,
    )
    audit = AuditEvent(
        id=str(uuid4()),
        actor_id=author_id,
        action="create_post",
        post_id=post.id,
        at=now,
    )
    try:
        db.add(post)
        db.flush()
        db.add(audit)
        db.flush()
    except SQLAlchemyError as exc:
        db.rollback()
        raise StorageError("Could not save the post. Try again in a moment.") from exc
    return post


def refresh_news_publication(db: Session, post: Post) -> None:
    blocks = db.scalars(
        select(NewsBlock).where(NewsBlock.post_id == post.id).order_by(NewsBlock.position.asc())
    ).all()
    live = [block for block in blocks if block.published_body is not None and block.published_heading]
    if not live:
        post.status = "draft"
        post.body = ""
        post.excerpt = ""
    else:
        parts = [f"{block.published_heading}\n\n{block.published_body}".strip() for block in live]
        post.body = "\n\n".join(parts)
        post.excerpt = make_excerpt(live[0].published_body or live[0].published_heading or "")
        post.status = "published"
    post.updated_at = utc_now()
    db.flush()


def delete_post_graph(db: Session, post: Post) -> None:
    post_id = post.id
    try:
        db.execute(delete(Comment).where(Comment.post_id == post_id, Comment.parent_id.is_not(None)))
        db.execute(delete(Comment).where(Comment.post_id == post_id))
        db.execute(delete(PostLike).where(PostLike.post_id == post_id))
        db.execute(delete(AuditEvent).where(AuditEvent.post_id == post_id))
        db.execute(delete(NewsBlock).where(NewsBlock.post_id == post_id))
        db.delete(post)
        db.flush()
    except SQLAlchemyError as exc:
        raise StorageError() from exc
