import json
import os
import re
from pathlib import Path
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import case, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from avatars import ALLOWED_TYPES, MAX_POST_IMAGE_BYTES, delete_post_image, delete_post_images, dump_images, normalize_avatar, parse_images, save_post_image
from deps import get_core_db, get_db, get_moderator, get_newsroom_user, get_super_admin, require_not_muted
from errors import ApiError, StorageError, forbidden, validation_error
from models import NewsBlock, NewsCategory, Post, User, to_iso, utc_now
from schemas import AuthorPublic, PatchNewsSubmissionBody, PublishNewsSubmissionBody, RemoveNewsSubmissionImageBody, PostDetail, PostList, PostSummary
from store import create_news_draft, make_excerpt, refresh_news_publication, users_by_ids
from validate import parse_page, parse_page_size, parse_uuid

router = APIRouter()
TOPICS = {"sport", "dorm", "scoop"}


def _categories(db: Session, post_id: str) -> list[str]:
    return ["scoop" if row.topic == "school" else row.topic for row in db.scalars(select(NewsCategory).where(NewsCategory.post_id == post_id)).all()]


def _article_block(db: Session, post_id: str) -> NewsBlock:
    block = db.scalar(select(NewsBlock).where(NewsBlock.post_id == post_id).order_by(NewsBlock.position.asc()))
    if block is None:
        raise ApiError(404, "not_found", "News article not found.")
    return block


def _require_article(db: Session, post_id: str) -> Post:
    post = db.scalar(
        select(Post).where(Post.id == post_id, Post.category == "news", Post.id.in_(select(NewsCategory.post_id)))
    )
    if post is None:
        raise ApiError(404, "not_found", "News article not found.")
    return post


def _require_owner(user: User, post: Post) -> None:
    if user.role != "super_admin" and post.author_id != user.id:
        raise forbidden()


def _submission(db: Session, core: Session, post: Post) -> dict:
    block = _article_block(db, post.id)
    author = users_by_ids(core, [post.author_id]).get(post.author_id)
    topics = _categories(db, post.id)
    images = parse_images(post.images, limit=None)
    return {
        "id": post.id,
        "title": post.title,
        "body": block.draft_body,
        "formatted_body": block.formatted_body,
        "format_source": getattr(block, "format_source", None),
        "topics": topics,
        "images": images,
        "status": "pending" if block.review_status == "pending" else post.status,
        "author": AuthorPublic(
            id=post.author_id,
            display_name=author.display_name if author else "Unknown",
            avatar=normalize_avatar(getattr(author, "avatar", None)),
        ).model_dump(),
        "created_at": to_iso(post.created_at),
        "updated_at": to_iso(post.updated_at),
    }


def _validate_article(title: str, body: str, topics: list[str]) -> list[dict[str, str]]:
    fields = []
    if not title.strip() or len(title.strip()) > 120:
        fields.append({"field": "title", "message": "Title must be 1–120 characters."})
    if not body.strip() or len(body.strip()) > 20000:
        fields.append({"field": "body", "message": "Body must be 1–20000 characters."})
    valid_topics = isinstance(topics, list) and all(isinstance(topic, str) for topic in topics)
    if not valid_topics or not topics or len(topics) > len(TOPICS) or len(set(topics)) != len(topics) or set(topics) - TOPICS:
        fields.append({"field": "topics", "message": "Choose one or more of Sports, Dorm, and Scoop."})
    return fields


def _post_summary(db: Session, core: Session, post: Post) -> PostSummary:
    author = users_by_ids(core, [post.author_id]).get(post.author_id)
    return PostSummary(
        id=post.id,
        title=post.title,
        excerpt=post.excerpt,
        category="news",
        status=post.status,
        created_at=to_iso(post.created_at),
        updated_at=to_iso(post.updated_at),
        author=AuthorPublic(
            id=post.author_id,
            display_name=author.display_name if author else "Unknown",
            avatar=normalize_avatar(getattr(author, "avatar", None)),
        ),
        reply_count=0,
        reply_preview=[],
        images=parse_images(post.images, limit=None),
        news_categories=_categories(db, post.id),
        like_count=0,
        liked=False,
        pinned=bool(post.pinned),
    )


@router.get("/news/articles")
def list_articles(
    db: Session = Depends(get_db),
    core: Session = Depends(get_core_db),
    topic: str = Query(default="all"),
    page: str | None = Query(default=None),
    page_size: str | None = Query(default=None),
):
    if topic not in {"all", *TOPICS, "school"}:
        raise validation_error([{"field": "topic", "message": "Choose all, sport, dorm, or scoop."}])
    if topic == "school":
        topic = "scoop"
    parsed_page = parse_page(page)
    parsed_size = parse_page_size(page_size)
    filters = [Post.category == "news", Post.status == "published", Post.id.in_(select(NewsCategory.post_id))]
    if topic != "all":
        matching_ids = select(NewsCategory.post_id).where(NewsCategory.topic.in_([topic, "school"] if topic == "scoop" else [topic]))
        filters.append(Post.id.in_(matching_ids))
    try:
        pin_rank = case((Post.pinned.is_(True), 0), else_=1)
        rows = db.scalars(
            select(Post)
            .where(*filters)
            .order_by(pin_rank.asc(), Post.pinned_at.desc(), Post.updated_at.desc(), Post.created_at.desc())
            .offset((parsed_page - 1) * parsed_size)
            .limit(parsed_size)
        ).all()
        total = db.query(Post).filter(*filters).count()
    except SQLAlchemyError as exc:
        raise StorageError() from exc
    return PostList(
        items=[_post_summary(db, core, post) for post in rows],
        page=parsed_page,
        page_size=parsed_size,
        total=total,
    ).model_dump()


@router.get("/news/articles/{article_id}")
def get_article(article_id: str, db: Session = Depends(get_db), core: Session = Depends(get_core_db)):
    post = _require_article(db, parse_uuid(article_id, "article_id"))
    if post.status != "published":
        raise ApiError(404, "not_found", "News article not found.")
    block = _article_block(db, post.id)
    author = users_by_ids(core, [post.author_id]).get(post.author_id)
    summary = _post_summary(db, core, post)
    return PostDetail(
        **summary.model_dump(),
        body=block.published_body or "",
        blocks=[],
    ).model_dump()


@router.get("/news/submissions")
def list_submissions(user: User = Depends(get_newsroom_user), db: Session = Depends(get_db), core: Session = Depends(get_core_db)):
    query = select(Post).where(Post.category == "news", Post.id.in_(select(NewsCategory.post_id)))
    if user.role != "super_admin":
        query = query.where(Post.author_id == user.id)
    try:
        posts = db.scalars(query.order_by(Post.updated_at.desc())).all()
    except SQLAlchemyError as exc:
        raise StorageError() from exc
    return {"items": [_submission(db, core, post) for post in posts]}


@router.post("/news/submissions", status_code=201)
async def create_submission(
    title: str = Form(...),
    body: str = Form(...),
    topics: str = Form(...),
    images: list[UploadFile] = File(default=[]),
    user: User = Depends(get_newsroom_user),
    db: Session = Depends(get_db),
    core: Session = Depends(get_core_db),
):
    require_not_muted(user)
    try:
        parsed_topics = json.loads(topics)
    except (TypeError, json.JSONDecodeError):
        parsed_topics = []
    if not isinstance(parsed_topics, list):
        parsed_topics = []
    fields = _validate_article(title, body, parsed_topics)
    uploads: list[tuple[str, bytes]] = []
    for image in images:
        ext = ALLOWED_TYPES.get((image.content_type or "").split(";")[0].strip().lower())
        data = await image.read()
        if ext is None or not data or len(data) > MAX_POST_IMAGE_BYTES:
            fields.append({"field": "images", "message": "Images must be jpeg, png, or webp and at most 2MB each."})
        else:
            uploads.append((ext, data))
    if fields:
        raise validation_error(fields)
    post = create_news_draft(db, author_id=user.id, title=title.strip())
    now = utc_now()
    block = NewsBlock(
        id=str(uuid4()), post_id=post.id, position=1, heading=title.strip(),
        published_heading=None, draft_body=body.strip(), formatted_body=None,
        published_body=None, review_status="editing", created_at=now, updated_at=now,
    )
    try:
        db.add(block)
        db.add_all([NewsCategory(post_id=post.id, topic=topic) for topic in sorted(set(parsed_topics))])
        if uploads:
            post.images = dump_images([save_post_image(post.id, ext, data) for ext, data in uploads], limit=None)
        db.flush()
    except (SQLAlchemyError, OSError) as exc:
        db.rollback()
        delete_post_images(post.id)
        raise StorageError() from exc
    return JSONResponse(status_code=201, content=_submission(db, core, post))


@router.patch("/news/submissions/{submission_id}")
def patch_submission(
    submission_id: str,
    body: PatchNewsSubmissionBody,
    user: User = Depends(get_newsroom_user),
    db: Session = Depends(get_db),
    core: Session = Depends(get_core_db),
):
    require_not_muted(user)
    post = _require_article(db, parse_uuid(submission_id))
    _require_owner(user, post)
    block = _article_block(db, post.id)
    if post.status != "draft" or block.review_status != "editing":
        raise validation_error([{"field": "status", "message": "Only draft submissions can be edited."}])
    title = body.title if body.title is not None else post.title
    text = body.body if body.body is not None else block.draft_body
    topics = body.topics if body.topics is not None else _categories(db, post.id)
    fields = _validate_article(title, text, topics)
    if fields:
        raise validation_error(fields)
    if body.title is not None:
        post.title = title.strip()
        block.heading = title.strip()
    if body.body is not None:
        block.draft_body = text.strip()
    if body.title is not None or body.body is not None:
        block.formatted_body = None
    if body.topics is not None:
        db.query(NewsCategory).filter(NewsCategory.post_id == post.id).delete(synchronize_session=False)
        db.add_all([NewsCategory(post_id=post.id, topic=topic) for topic in sorted(set(topics))])
    post.updated_at = block.updated_at = utc_now()
    block.review_status = "editing"
    return _submission(db, core, post)


@router.post("/news/submissions/{submission_id}/images")
async def add_submission_images(
    submission_id: str,
    images: list[UploadFile] = File(...),
    user: User = Depends(get_newsroom_user),
    db: Session = Depends(get_db),
    core: Session = Depends(get_core_db),
):
    require_not_muted(user)
    post = _require_article(db, parse_uuid(submission_id))
    _require_owner(user, post)
    block = _article_block(db, post.id)
    if post.status != "draft" or block.review_status != "editing":
        raise validation_error([{"field": "status", "message": "Only draft submissions can receive images."}])

    existing = parse_images(post.images, limit=None)
    fields = []
    if not images:
        fields.append({"field": "images", "message": "Choose at least one image."})
    uploads: list[tuple[str, bytes]] = []
    for image in images:
        ext = ALLOWED_TYPES.get((image.content_type or "").split(";")[0].strip().lower())
        data = await image.read()
        if ext is None or not data or len(data) > MAX_POST_IMAGE_BYTES:
            fields.append({"field": "images", "message": "Images must be jpeg, png, or webp and at most 2MB each."})
        else:
            uploads.append((ext, data))
    if fields:
        raise validation_error(fields)

    saved: list[str] = []
    try:
        saved = [save_post_image(post.id, ext, data) for ext, data in uploads]
        post.images = dump_images([*existing, *saved], limit=None)
        post.updated_at = block.updated_at = utc_now()
        db.flush()
    except (SQLAlchemyError, OSError) as exc:
        db.rollback()
        root = Path(__file__).resolve().parents[1]
        for image_path in saved:
            (root / image_path.lstrip("/")).unlink(missing_ok=True)
        raise StorageError() from exc
    return _submission(db, core, post)


@router.delete("/news/submissions/{submission_id}/images")
def remove_submission_image(
    submission_id: str,
    body: RemoveNewsSubmissionImageBody,
    user: User = Depends(get_newsroom_user),
    db: Session = Depends(get_db),
    core: Session = Depends(get_core_db),
):
    require_not_muted(user)
    post = _require_article(db, parse_uuid(submission_id))
    _require_owner(user, post)
    block = _article_block(db, post.id)
    if post.status != "draft" or block.review_status != "editing":
        raise validation_error([{"field": "status", "message": "Only draft submissions can remove images."}])
    image = body.image
    images = parse_images(post.images, limit=None)
    if not isinstance(image, str) or image not in images:
        raise validation_error([{"field": "image", "message": "Choose an image attached to this draft."}])
    post.images = dump_images([path for path in images if path != image], limit=None)
    post.updated_at = block.updated_at = utc_now()
    db.flush()
    delete_post_image(post.id, image)
    return _submission(db, core, post)


def _local_format(text: str) -> str:
    paragraphs = [re.sub(r"[ \t]+", " ", part).strip() for part in re.split(r"\n\s*\n", text.replace("\r\n", "\n"))]
    return "\n\n".join(part for part in paragraphs if part)


@router.post("/news/submissions/{submission_id}/format")
async def format_submission(
    submission_id: str,
    user: User = Depends(get_super_admin),
    db: Session = Depends(get_db),
    core: Session = Depends(get_core_db),
):
    require_not_muted(user)
    post = _require_article(db, parse_uuid(submission_id))
    if post.status != "draft":
        raise validation_error([{"field": "status", "message": "Only draft submissions can be formatted."}])
    block = _article_block(db, post.id)
    if block.review_status != "editing":
        raise validation_error([{"field": "status", "message": "Only draft submissions can be formatted."}])
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        block.formatted_body = _local_format(block.draft_body)
        block.format_source = "local"
    else:
        model = os.environ.get("NEWS_AI_MODEL", "gpt-4o-mini").strip()
        prompt = (
            "Edit the following news article for readable paragraph layout. Preserve all facts, "
            "names, quotations, and meaning. Do not add claims. Return only the edited article body.\n\n"
            f"Title: {post.title}\nBody:\n{block.draft_body}"
        )
        try:
            async with httpx.AsyncClient(timeout=45) as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.2},
                )
            response.raise_for_status()
            formatted = response.json()["choices"][0]["message"]["content"].strip()
            if not formatted or len(formatted) > 20000:
                raise ValueError("Invalid formatted article.")
            block.formatted_body = formatted
            block.format_source = "openai"
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise ApiError(502, "ai_unavailable", "The AI formatter could not complete this request.") from exc
    post.updated_at = block.updated_at = utc_now()
    return _submission(db, core, post)


@router.post("/news/submissions/{submission_id}/submit")
def submit_submission(
    submission_id: str,
    body: PublishNewsSubmissionBody = PublishNewsSubmissionBody(),
    user: User = Depends(get_newsroom_user),
    db: Session = Depends(get_db),
    core: Session = Depends(get_core_db),
):
    require_not_muted(user)
    post = _require_article(db, parse_uuid(submission_id))
    _require_owner(user, post)
    block = _article_block(db, post.id)
    if post.status != "draft" or block.review_status != "editing":
        raise validation_error([{"field": "status", "message": "This submission is not a draft."}])
    if body.mode not in {"original", "formatted"}:
        raise validation_error([{"field": "mode", "message": "Choose original or formatted copy."}])
    if body.mode == "formatted" and not block.formatted_body:
        raise validation_error([{"field": "mode", "message": "Design this story before submitting formatted copy."}])
    if body.mode == "original":
        block.formatted_body = None
        block.format_source = None
    block.review_status = "pending"
    post.updated_at = block.updated_at = utc_now()
    return _submission(db, core, post)


@router.get("/news/review")
def list_review(db: Session = Depends(get_db), core: Session = Depends(get_core_db), _: User = Depends(get_super_admin)):
    pending_ids = select(NewsBlock.post_id).where(NewsBlock.review_status == "pending")
    try:
        posts = db.scalars(select(Post).where(Post.id.in_(pending_ids), Post.id.in_(select(NewsCategory.post_id))).order_by(Post.updated_at.asc())).all()
    except SQLAlchemyError as exc:
        raise StorageError() from exc
    return {"items": [_submission(db, core, post) for post in posts]}


@router.get("/news/review/{submission_id}")
def get_review_submission(
    submission_id: str,
    db: Session = Depends(get_db),
    core: Session = Depends(get_core_db),
    _: User = Depends(get_super_admin),
):
    post = _require_article(db, parse_uuid(submission_id))
    block = _article_block(db, post.id)
    if block.review_status != "pending":
        raise ApiError(404, "not_found", "Pending News article not found.")
    return _submission(db, core, post)


@router.post("/news/submissions/{submission_id}/approve")
def approve_submission(submission_id: str, user: User = Depends(get_super_admin), db: Session = Depends(get_db), core: Session = Depends(get_core_db)):
    post = _require_article(db, parse_uuid(submission_id))
    block = _article_block(db, post.id)
    if block.review_status != "pending":
        raise validation_error([{"field": "status", "message": "Only pending submissions can be approved."}])
    block.published_heading = post.title
    block.published_body = block.formatted_body or block.draft_body
    block.review_status = "published"
    block.updated_at = utc_now()
    refresh_news_publication(db, post)
    return _submission(db, core, post)


@router.post("/news/submissions/{submission_id}/publish")
def publish_submission(
    submission_id: str,
    body: PublishNewsSubmissionBody,
    user: User = Depends(get_super_admin),
    db: Session = Depends(get_db),
    core: Session = Depends(get_core_db),
):
    post = _require_article(db, parse_uuid(submission_id))
    block = _article_block(db, post.id)
    if post.status != "draft" or block.review_status not in {"editing", "pending"}:
        raise validation_error([{"field": "status", "message": "Only unpublished submissions can be published."}])
    if body.mode not in {"original", "formatted"}:
        raise validation_error([{"field": "mode", "message": "Choose original or formatted copy."}])
    if body.mode == "formatted" and not block.formatted_body:
        raise validation_error([{"field": "mode", "message": "Design this story before publishing formatted copy."}])
    block.published_heading = post.title
    block.published_body = block.formatted_body if body.mode == "formatted" else block.draft_body
    block.review_status = "published"
    block.updated_at = utc_now()
    refresh_news_publication(db, post)
    return _submission(db, core, post)


@router.post("/news/submissions/{submission_id}/withdraw")
def withdraw_submission(
    submission_id: str,
    _user: User = Depends(get_moderator),
    db: Session = Depends(get_db),
    core: Session = Depends(get_core_db),
):
    post = _require_article(db, parse_uuid(submission_id))
    block = _article_block(db, post.id)
    if post.status != "published" or block.review_status != "published":
        raise validation_error([{"field": "status", "message": "Only published articles can be withdrawn."}])
    block.published_heading = None
    block.published_body = None
    block.review_status = "editing"
    block.updated_at = utc_now()
    refresh_news_publication(db, post)
    return _submission(db, core, post)


@router.post("/news/submissions/{submission_id}/reject")
def reject_submission(submission_id: str, user: User = Depends(get_super_admin), db: Session = Depends(get_db), core: Session = Depends(get_core_db)):
    post = _require_article(db, parse_uuid(submission_id))
    block = _article_block(db, post.id)
    if block.review_status != "pending":
        raise validation_error([{"field": "status", "message": "Only pending submissions can be returned."}])
    block.review_status = "editing"
    post.status = "draft"
    post.updated_at = block.updated_at = utc_now()
    return _submission(db, core, post)
