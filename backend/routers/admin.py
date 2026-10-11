from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from avatars import delete_post_images, normalize_avatar
from deps import get_core_db, get_db, get_super_admin
from errors import ApiError, StorageError, forbidden, validation_error
from models import User, to_iso
from schemas import ASSIGNABLE_ROLES, PatchUserRoleBody, UserList, UserPrivate
from store import delete_user_account
from validate import parse_page, parse_page_size, parse_uuid

router = APIRouter()


def _user_private(user: User) -> dict:
    return UserPrivate(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        avatar=normalize_avatar(getattr(user, "avatar", None)),
        muted=bool(user.muted),
        terms_accepted_at=to_iso(user.terms_accepted_at) if user.terms_accepted_at else None,
        created_at=to_iso(user.created_at),
    ).model_dump()


def _load_target(db: Session, user_id: str) -> User:
    try:
        target = db.scalar(select(User).where(User.id == user_id))
    except SQLAlchemyError as exc:
        raise StorageError() from exc
    if target is None:
        raise ApiError(404, "not_found", "User not found.")
    return target


@router.get("/admin/users")
def list_users(
    _: User = Depends(get_super_admin),
    db: Session = Depends(get_core_db),
    page: str | None = Query(default=None),
    page_size: str | None = Query(default=None),
):
    parsed_page = parse_page(page)
    parsed_size = parse_page_size(page_size)
    try:
        total = db.scalar(select(func.count()).select_from(User)) or 0
        rows = db.scalars(
            select(User)
            .order_by(User.created_at.desc())
            .offset((parsed_page - 1) * parsed_size)
            .limit(parsed_size)
        ).all()
    except SQLAlchemyError as exc:
        raise StorageError() from exc
    return UserList(
        items=[UserPrivate(**_user_private(user)) for user in rows],
        page=parsed_page,
        page_size=parsed_size,
        total=total,
    ).model_dump()


@router.patch("/admin/users/{user_id}")
def patch_user_role(
    user_id: str,
    body: PatchUserRoleBody,
    actor: User = Depends(get_super_admin),
    db: Session = Depends(get_core_db),
):
    user_id = parse_uuid(user_id, "user_id")
    if body.role is None and body.muted is None:
        raise validation_error(
            [{"field": "role", "message": "Provide a role or a muted flag."}]
        )
    if body.role is not None and body.role not in ASSIGNABLE_ROLES:
        raise validation_error(
            [{"field": "role", "message": "Must be one of: student, teacher, editor, admin."}]
        )
    target = _load_target(db, user_id)
    if target.role == "super_admin":
        raise forbidden("Super-admin accounts cannot be changed here.")
    if body.muted is True and target.id == actor.id:
        raise forbidden("You cannot mute your own account.")
    if body.role is not None:
        target.role = body.role
    if body.muted is not None:
        target.muted = body.muted
    return _user_private(target)


@router.delete("/admin/users/{user_id}", status_code=204)
def delete_user(
    user_id: str,
    actor: User = Depends(get_super_admin),
    db: Session = Depends(get_core_db),
    content: Session = Depends(get_db),
):
    user_id = parse_uuid(user_id, "user_id")
    target = _load_target(db, user_id)
    if target.id == actor.id:
        raise forbidden("You cannot delete your own account.")
    if target.role == "super_admin":
        raise forbidden("Super-admin accounts cannot be deleted here.")
    post_ids = delete_user_account(db, content, target)
    for post_id in post_ids:
        delete_post_images(post_id)
