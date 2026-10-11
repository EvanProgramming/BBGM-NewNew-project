from uuid import uuid4

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from avatars import normalize_avatar
from deps import get_core_db, get_db, get_newsroom_user, get_super_admin, require_not_muted
from errors import ApiError, StorageError, validation_error
from models import NewsBlock, NewsCategory, Post, User, to_iso, utc_now
from schemas import (
    AuthorPublic,
    CreateBlockBody,
    CreateDraftBody,
    NewsBlockStaff,
    NewsDraftDetail,
    NewsDraftList,
    NewsDraftSummary,
    PatchBlockBody,
)
from store import create_news_draft, refresh_news_publication, users_by_ids
from validate import parse_page, parse_page_size, parse_uuid

router = APIRouter()


def _author(user: User) -> AuthorPublic:
    return AuthorPublic(
        id=user.id,
        display_name=user.display_name,
        avatar=normalize_avatar(getattr(user, "avatar", None)),
    )


def _author_public(user: User | None, author_id: str) -> AuthorPublic:
    if user is None:
        return AuthorPublic(id=author_id, display_name="Unknown", avatar="preset:oak")
    return _author(user)


def _block_staff(block: NewsBlock) -> NewsBlockStaff:
    return NewsBlockStaff(
        id=block.id,
        position=block.position,
        heading=block.heading,
        draft_body=block.draft_body,
        published_heading=block.published_heading,
        published_body=block.published_body,
        review_status=block.review_status,
    )


def _blocks_for(db: Session, post_id: str) -> list[NewsBlock]:
    return list(
        db.scalars(
            select(NewsBlock).where(NewsBlock.post_id == post_id).order_by(NewsBlock.position.asc())
        ).all()
    )


def _draft_detail(db: Session, post: Post, author: User | None) -> dict:
    blocks = _blocks_for(db, post.id)
    return NewsDraftDetail(
        id=post.id,
        title=post.title,
        status=post.status,
        created_at=to_iso(post.created_at),
        updated_at=to_iso(post.updated_at),
        author=_author_public(author, post.author_id),
        blocks=[_block_staff(block) for block in blocks],
    ).model_dump()


def _author_for(core: Session, post: Post) -> User | None:
    return users_by_ids(core, [post.author_id]).get(post.author_id)


def _load_draft(db: Session, draft_id: str) -> Post:
    try:
        post = db.scalar(
            select(Post).where(
                Post.id == draft_id,
                Post.category == "news",
                Post.id.not_in(select(NewsCategory.post_id)),
            )
        )
    except SQLAlchemyError as exc:
        raise StorageError() from exc
    if post is None:
        raise ApiError(404, "not_found", "Draft not found.")
    return post


def _load_block(db: Session, post_id: str, block_id: str) -> NewsBlock:
    try:
        block = db.scalar(
            select(NewsBlock).where(NewsBlock.id == block_id, NewsBlock.post_id == post_id)
        )
    except SQLAlchemyError as exc:
        raise StorageError() from exc
    if block is None:
        raise ApiError(404, "not_found", "Block not found.")
    return block


def _heading_error(value: str) -> dict[str, str] | None:
    text = value.strip()
    if not text or len(text) > 120:
        return {"field": "heading", "message": "Heading must be 1–120 characters."}
    return None


def _body_error(value: str) -> dict[str, str] | None:
    text = value.strip()
    if not text or len(text) > 20000:
        return {"field": "body", "message": "Body must be 1–20000 characters."}
    return None


def _position_error(value: int) -> dict[str, str] | None:
    if value < 1 or value > 16:
        return {"field": "position", "message": "Position must be from 1 to 16."}
    return None


@router.get("/news/drafts")
def list_drafts(
    _: User = Depends(get_newsroom_user),
    db: Session = Depends(get_db),
    core: Session = Depends(get_core_db),
    page: str | None = Query(default=None),
    page_size: str | None = Query(default=None),
):
    parsed_page = parse_page(page)
    parsed_size = parse_page_size(page_size)
    try:
        draft_filter = (Post.category == "news", Post.id.not_in(select(NewsCategory.post_id)))
        total = db.scalar(select(func.count()).select_from(Post).where(*draft_filter)) or 0
        rows = db.scalars(
            select(Post)
            .where(*draft_filter)
            .order_by(Post.updated_at.desc())
            .offset((parsed_page - 1) * parsed_size)
            .limit(parsed_size)
        ).all()
    except SQLAlchemyError as exc:
        raise StorageError() from exc
    authors = users_by_ids(core, [post.author_id for post in rows])
    return NewsDraftList(
        items=[
            NewsDraftSummary(
                id=post.id,
                title=post.title,
                status=post.status,
                created_at=to_iso(post.created_at),
                updated_at=to_iso(post.updated_at),
                author=_author_public(authors.get(post.author_id), post.author_id),
            )
            for post in rows
        ],
        page=parsed_page,
        page_size=parsed_size,
        total=total,
    ).model_dump()


@router.post("/news/drafts", status_code=201)
def create_draft(
    body: CreateDraftBody,
    user: User = Depends(get_newsroom_user),
    db: Session = Depends(get_db),
):
    require_not_muted(user)
    title = body.title.strip()
    if not title or len(title) > 120:
        raise validation_error([{"field": "title", "message": "Title must be 1–120 characters."}])
    post = create_news_draft(db, author_id=user.id, title=title)
    return JSONResponse(status_code=201, content=_draft_detail(db, post, user))


@router.get("/news/drafts/{draft_id}")
def get_draft(
    draft_id: str,
    _: User = Depends(get_newsroom_user),
    db: Session = Depends(get_db),
    core: Session = Depends(get_core_db),
):
    post = _load_draft(db, parse_uuid(draft_id, "draft_id"))
    return _draft_detail(db, post, _author_for(core, post))


@router.post("/news/drafts/{draft_id}/blocks", status_code=201)
def add_block(
    draft_id: str,
    body: CreateBlockBody,
    user: User = Depends(get_newsroom_user),
    db: Session = Depends(get_db),
    core: Session = Depends(get_core_db),
):
    require_not_muted(user)
    post = _load_draft(db, parse_uuid(draft_id, "draft_id"))
    fields = [item for item in (_heading_error(body.heading), _body_error(body.body)) if item]
    if body.position is not None:
        error = _position_error(body.position)
        if error:
            fields.append(error)
    if fields:
        raise validation_error(fields)
    try:
        if body.position is None:
            last = db.scalar(select(func.max(NewsBlock.position)).where(NewsBlock.post_id == post.id)) or 0
            position = int(last) + 1
            error = _position_error(position)
            if error:
                raise validation_error([error])
        else:
            position = body.position
            taken = db.scalar(
                select(NewsBlock.id).where(
                    NewsBlock.post_id == post.id,
                    NewsBlock.position == position,
                )
            )
            if taken is not None:
                raise validation_error(
                    [{"field": "position", "message": "This slot already has a section."}]
                )
        now = utc_now()
        block = NewsBlock(
            id=str(uuid4()),
            post_id=post.id,
            position=position,
            heading=body.heading.strip(),
            published_heading=None,
            draft_body=body.body.strip(),
            published_body=None,
            review_status="editing",
            created_at=now,
            updated_at=now,
        )
        db.add(block)
        post.updated_at = now
        db.flush()
    except SQLAlchemyError as exc:
        raise StorageError() from exc
    return JSONResponse(status_code=201, content=_draft_detail(db, post, _author_for(core, post)))


@router.patch("/news/drafts/{draft_id}/blocks/{block_id}")
def patch_block(
    draft_id: str,
    block_id: str,
    body: PatchBlockBody,
    user: User = Depends(get_newsroom_user),
    db: Session = Depends(get_db),
    core: Session = Depends(get_core_db),
):
    require_not_muted(user)
    post = _load_draft(db, parse_uuid(draft_id, "draft_id"))
    block = _load_block(db, post.id, parse_uuid(block_id, "block_id"))
    if body.heading is None and body.body is None:
        raise validation_error([{"field": "heading", "message": "Provide a heading or a body."}])
    fields = []
    if body.heading is not None:
        error = _heading_error(body.heading)
        if error:
            fields.append(error)
    if body.body is not None:
        error = _body_error(body.body)
        if error:
            fields.append(error)
    if fields:
        raise validation_error(fields)
    if body.heading is not None:
        block.heading = body.heading.strip()
    if body.body is not None:
        block.draft_body = body.body.strip()
    block.review_status = "editing"
    now = utc_now()
    block.updated_at = now
    post.updated_at = now
    return _draft_detail(db, post, _author_for(core, post))


@router.post("/news/drafts/{draft_id}/blocks/{block_id}/submit")
def submit_block(
    draft_id: str,
    block_id: str,
    user: User = Depends(get_newsroom_user),
    db: Session = Depends(get_db),
    core: Session = Depends(get_core_db),
):
    require_not_muted(user)
    post = _load_draft(db, parse_uuid(draft_id, "draft_id"))
    block = _load_block(db, post.id, parse_uuid(block_id, "block_id"))
    block.review_status = "pending"
    now = utc_now()
    block.updated_at = now
    post.updated_at = now
    return _draft_detail(db, post, _author_for(core, post))


def _require_pending(block: NewsBlock) -> None:
    if block.review_status != "pending":
        raise validation_error(
            [{"field": "review_status", "message": "Submit this block before it can be reviewed."}]
        )


@router.post("/news/drafts/{draft_id}/blocks/{block_id}/approve")
def approve_block(
    draft_id: str,
    block_id: str,
    _: User = Depends(get_super_admin),
    db: Session = Depends(get_db),
    core: Session = Depends(get_core_db),
):
    post = _load_draft(db, parse_uuid(draft_id, "draft_id"))
    block = _load_block(db, post.id, parse_uuid(block_id, "block_id"))
    _require_pending(block)
    block.published_heading = block.heading
    block.published_body = block.draft_body
    block.review_status = "published"
    now = utc_now()
    block.updated_at = now
    refresh_news_publication(db, post)
    return _draft_detail(db, post, _author_for(core, post))


@router.post("/news/drafts/{draft_id}/blocks/{block_id}/reject")
def reject_block(
    draft_id: str,
    block_id: str,
    _: User = Depends(get_super_admin),
    db: Session = Depends(get_db),
    core: Session = Depends(get_core_db),
):
    post = _load_draft(db, parse_uuid(draft_id, "draft_id"))
    block = _load_block(db, post.id, parse_uuid(block_id, "block_id"))
    _require_pending(block)
    block.review_status = "editing"
    now = utc_now()
    block.updated_at = now
    post.updated_at = now
    return _draft_detail(db, post, _author_for(core, post))
