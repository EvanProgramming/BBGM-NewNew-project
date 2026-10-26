from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile as StarletteUploadFile
from starlette.exceptions import HTTPException as StarletteHTTPException

from deps import get_core_db, get_current_user, get_db, get_optional_user, get_super_admin, require_not_muted
from errors import ApiError, StorageError, forbidden, unauthenticated, validation_error
from identity import user_has
from avatars import (
    ALLOWED_TYPES,
    MAX_POST_IMAGE_BYTES,
    MAX_POST_IMAGES,
    delete_post_images,
    dump_images,
    normalize_avatar,
    parse_images,
    save_post_image,
)
from models import Comment, NewsBlock, NewsCategory, Post, PostLike, User, to_iso, utc_now
from schemas import (
    CATEGORIES,
    CATEGORY_MESSAGE,
    NEWSPAPER_CATEGORIES,
    AuthorPublic,
    CommentFloor,
    CommentList,
    CommentReply,
    CreateCommentBody,
    CreatePostBody,
    LikeState,
    MODERATOR_ROLES,
    PinPostBody,
    PostDetail,
    PostList,
    PostSummary,
    PublishedBlock,
    ReplyPreview,
)
from store import (
    add_like,
    add_system_notice,
    count_likes,
    create_comment,
    create_post_with_audit,
    delete_comment,
    delete_post_graph,
    like_counts_for_posts,
    liked_post_ids,
    remove_like,
    user_liked,
    users_by_ids,
)
from validate import (
    parse_forum_feed,
    parse_forum_query,
    parse_optional_category,
    parse_page,
    parse_page_size,
    parse_uuid,
)

router = APIRouter()


def _author_public(user: User | None, author_id: str = "") -> AuthorPublic:
    if user is None:
        return AuthorPublic(id=author_id, display_name="Unknown", avatar="preset:oak")
    return AuthorPublic(
        id=user.id,
        display_name=user.display_name,
        avatar=normalize_avatar(getattr(user, "avatar", None)),
    )


def _summary(
    post: Post,
    *,
    author: User | None = None,
    reply_count: int = 0,
    reply_preview: list[ReplyPreview] | None = None,
    include_images: bool = False,
    news_categories: list[str] | None = None,
    like_count: int = 0,
    liked: bool = False,
) -> PostSummary:
    images = parse_images(getattr(post, "images", None), limit=None if post.category == "news" else MAX_POST_IMAGES) if include_images else []
    return PostSummary(
        id=post.id,
        title=post.title,
        excerpt=post.excerpt,
        category=post.category,
        status=post.status,
        created_at=to_iso(post.created_at),
        updated_at=to_iso(post.updated_at),
        author=_author_public(author, post.author_id),
        reply_count=reply_count,
        reply_preview=reply_preview or [],
        images=images,
        news_categories=news_categories or [],
        like_count=like_count if post.category == "forum" else 0,
        liked=liked if post.category == "forum" else False,
        pinned=bool(post.pinned),
    )


def _published_blocks(db: Session, post: Post) -> list[PublishedBlock]:
    if post.category != "news":
        return []
    rows = db.scalars(
        select(NewsBlock)
        .where(NewsBlock.post_id == post.id, NewsBlock.published_body.is_not(None))
        .order_by(NewsBlock.position.asc())
    ).all()
    return [
        PublishedBlock(
            id=row.id,
            heading=row.published_heading or row.heading,
            body=row.published_body or "",
            position=row.position,
        )
        for row in rows
        if row.published_heading
    ]


def _detail(
    post: Post,
    *,
    author: User | None = None,
    blocks: list[PublishedBlock] | None = None,
    like_count: int = 0,
    liked: bool = False,
    news_categories: list[str] | None = None,
    body: str | None = None,
) -> dict:
    return PostDetail(
        **_summary(
            post,
            author=author,
            include_images=True,
            news_categories=news_categories,
            like_count=like_count,
            liked=liked,
        ).model_dump(),
        body=post.body if body is None else body,
        blocks=blocks or [],
    ).model_dump()


def _any_post(db: Session, post_id: str) -> Post:
    try:
        post = db.scalar(select(Post).where(Post.id == post_id))
    except SQLAlchemyError as exc:
        raise StorageError() from exc
    if post is None:
        raise ApiError(404, "not_found", "Post not found.")
    return post


def _published_post(db: Session, post_id: str) -> Post:
    try:
        post = db.scalar(select(Post).where(Post.id == post_id, Post.status == "published"))
    except SQLAlchemyError as exc:
        raise StorageError() from exc
    if post is None:
        raise ApiError(404, "not_found", "Post not found.")
    return post


def _require_forum(post: Post) -> None:
    if post.category != "forum":
        raise validation_error(
            [{"field": "category", "message": "Comments are only available on forum posts."}]
        )


def _post_field_errors(body: CreatePostBody) -> list[dict[str, str]]:
    fields: list[dict[str, str]] = []
    title = body.title.strip()
    if not title or len(title) > 120:
        fields.append({"field": "title", "message": "Title must be 1–120 characters."})
    text = body.body.strip()
    if not text or len(text) > 20000:
        fields.append({"field": "body", "message": "Body must be 1–20000 characters."})
    if body.category not in CATEGORIES:
        fields.append({"field": "category", "message": CATEGORY_MESSAGE})
    return fields


def _keyword_rank(keyword: str):
    escaped = keyword.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    pattern = f"%{escaped}%"
    hit = or_(
        func.lower(Post.title).like(pattern, escape="\\"),
        func.lower(Post.body).like(pattern, escape="\\"),
    )
    return case((hit, 0), else_=1)


def _list_posts(
    db: Session,
    core: Session,
    *,
    page: int,
    page_size: int,
    category: str | None,
    author_id: str | None,
    viewer: User | None = None,
    feed: str | None = None,
    keyword: str | None = None,
) -> dict:
    filters = [Post.status == "published"]
    if category is not None:
        filters.append(Post.category == category)
    elif author_id is None:
        filters.append(Post.category.in_(NEWSPAPER_CATEGORIES))
        filters.append(Post.id.not_in(select(NewsCategory.post_id)))
    if author_id is not None:
        filters.append(Post.author_id == author_id)
    capped = feed in ("recommended", "latest")
    offset = 0 if capped else (page - 1) * page_size
    limit = 10 if capped else page_size
    if feed == "recommended":
        like_total = (
            select(func.count(PostLike.id))
            .where(PostLike.post_id == Post.id)
            .correlate(Post)
            .scalar_subquery()
        )
        comment_total = (
            select(func.count(Comment.id))
            .where(Comment.post_id == Post.id, Comment.parent_id.is_(None))
            .correlate(Post)
            .scalar_subquery()
        )
        score = like_total * 0.6 + comment_total * 0.4
        order = (score.desc(), Post.created_at.desc())
    else:
        order = (Post.created_at.desc(),)
    if author_id is None:
        rank = case((Post.pinned.is_(True), 0), else_=1)
        order = (rank.asc(), Post.pinned_at.desc(), *order)
    if keyword:
        order = (_keyword_rank(keyword), *order)
    try:
        total = db.scalar(select(func.count()).select_from(Post).where(*filters)) or 0
        rows = db.scalars(
            select(Post)
            .where(*filters)
            .order_by(*order)
            .offset(offset)
            .limit(limit)
        ).all()
    except SQLAlchemyError as exc:
        raise StorageError() from exc
    if capped:
        total = min(total, 10)
        page = 1
        page_size = 10
    previews = _forum_previews(db, core, rows) if category == "forum" else {}
    include_images = category in (None, "forum", "news")
    forum_ids = [post.id for post in rows if post.category == "forum"]
    like_counts = like_counts_for_posts(db, forum_ids)
    liked_ids = liked_post_ids(db, user_id=viewer.id, post_ids=forum_ids) if viewer else set()
    authors = users_by_ids(core, [post.author_id for post in rows])
    try:
        topic_rows = db.scalars(select(NewsCategory).where(NewsCategory.post_id.in_([p.id for p in rows]))).all() if rows else []
    except SQLAlchemyError as exc:
        raise StorageError() from exc
    topics: dict[str, list[str]] = {}
    for row in topic_rows:
        topics.setdefault(row.post_id, []).append(row.topic)
    return PostList(
        items=[
            _summary(
                post,
                author=authors.get(post.author_id),
                reply_count=previews.get(post.id, (0, []))[0],
                reply_preview=previews.get(post.id, (0, []))[1],
                include_images=include_images,
                news_categories=topics.get(post.id, []),
                like_count=like_counts.get(post.id, 0),
                liked=post.id in liked_ids,
            )
            for post in rows
        ],
        page=page,
        page_size=page_size,
        total=total,
    ).model_dump()


def _forum_previews(db: Session, core: Session, posts: list[Post]) -> dict[str, tuple[int, list[ReplyPreview]]]:
    ids = [post.id for post in posts if post.category == "forum"]
    if not ids:
        return {}
    try:
        floors = db.scalars(
            select(Comment)
            .where(Comment.post_id.in_(ids), Comment.parent_id.is_(None))
            .order_by(Comment.created_at.asc())
        ).all()
    except SQLAlchemyError as exc:
        raise StorageError() from exc
    authors = users_by_ids(core, [floor.author_id for floor in floors])
    grouped: dict[str, list[Comment]] = {}
    for floor in floors:
        grouped.setdefault(floor.post_id, []).append(floor)
    result: dict[str, tuple[int, list[ReplyPreview]]] = {}
    for post_id, items in grouped.items():
        result[post_id] = (
            len(items),
            [
                ReplyPreview(
                    id=item.id,
                    body=item.body,
                    created_at=to_iso(item.created_at),
                    author=_author_public(authors.get(item.author_id), item.author_id),
                )
                for item in items[-2:]
            ],
        )
    return result


def _floor_payload(comment: Comment, floor: int, replies: list[Comment], authors: dict[str, User]) -> dict:
    return CommentFloor(
        id=comment.id,
        body=comment.body,
        parent_id=None,
        floor=floor,
        created_at=to_iso(comment.created_at),
        author=_author_public(authors.get(comment.author_id), comment.author_id),
        replies=[
            CommentReply(
                id=reply.id,
                body=reply.body,
                parent_id=reply.parent_id or comment.id,
                created_at=to_iso(reply.created_at),
                author=_author_public(authors.get(reply.author_id), reply.author_id),
            )
            for reply in replies
        ],
    ).model_dump()


def _reply_payload(comment: Comment, authors: dict[str, User]) -> dict:
    return CommentReply(
        id=comment.id,
        body=comment.body,
        parent_id=comment.parent_id or "",
        created_at=to_iso(comment.created_at),
        author=_author_public(authors.get(comment.author_id), comment.author_id),
    ).model_dump()


@router.get("/posts")
def list_posts(
    db: Session = Depends(get_db),
    core: Session = Depends(get_core_db),
    viewer: User | None = Depends(get_optional_user),
    category: str | None = Query(default=None),
    feed: str | None = Query(default=None),
    q: str | None = Query(default=None),
    page: str | None = Query(default=None),
    page_size: str | None = Query(default=None),
):
    parsed_page = parse_page(page)
    parsed_size = parse_page_size(page_size)
    parsed_category = parse_optional_category(category)
    parsed_feed = parse_forum_feed(feed, parsed_category)
    parsed_q = parse_forum_query(q, parsed_category)
    if parsed_category == "forum" and viewer is None:
        raise unauthenticated()
    if parsed_feed in ("recommended", "latest") and parsed_page != 1:
        raise validation_error(
            [{"field": "page", "message": "This forum feed only has the first page."}]
        )
    return _list_posts(
        db,
        core,
        page=parsed_page,
        page_size=parsed_size,
        category=parsed_category,
        author_id=viewer.id if parsed_feed == "mine" and viewer is not None else None,
        viewer=viewer,
        feed=parsed_feed,
        keyword=parsed_q,
    )


@router.get("/posts/{post_id}/comments")
def list_comments(
    post_id: str,
    db: Session = Depends(get_db),
    core: Session = Depends(get_core_db),
    viewer: User | None = Depends(get_optional_user),
    page: str | None = Query(default=None),
    page_size: str | None = Query(default=None),
):
    post_id = parse_uuid(post_id)
    parsed_page = parse_page(page)
    parsed_size = parse_page_size(page_size)
    post = _published_post(db, post_id)
    _require_forum(post)
    if viewer is None:
        raise unauthenticated()

    floor_filter = [Comment.post_id == post_id, Comment.parent_id.is_(None)]
    try:
        total = db.scalar(select(func.count()).select_from(Comment).where(*floor_filter)) or 0
        floors = db.scalars(
            select(Comment)
            .where(*floor_filter)
            .order_by(Comment.created_at.asc())
            .offset((parsed_page - 1) * parsed_size)
            .limit(parsed_size)
        ).all()
        floor_ids = [item.id for item in floors]
        replies = []
        if floor_ids:
            replies = db.scalars(
                select(Comment)
                .where(Comment.post_id == post_id, Comment.parent_id.in_(floor_ids))
                .order_by(Comment.created_at.asc())
            ).all()
    except SQLAlchemyError as exc:
        raise StorageError() from exc

    authors = users_by_ids(
        core,
        [item.author_id for item in floors] + [item.author_id for item in replies],
    )
    grouped: dict[str, list[Comment]] = {item.id: [] for item in floors}
    for reply in replies:
        grouped.setdefault(reply.parent_id or "", []).append(reply)

    start = (parsed_page - 1) * parsed_size
    items = [
        _floor_payload(floor, start + index + 1, grouped.get(floor.id, []), authors)
        for index, floor in enumerate(floors)
    ]
    return CommentList(items=items, page=parsed_page, page_size=parsed_size, total=total).model_dump()


@router.post("/posts/{post_id}/comments", status_code=201)
def create_post_comment(
    post_id: str,
    body: CreateCommentBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_not_muted(user)
    post_id = parse_uuid(post_id)
    post = _published_post(db, post_id)
    _require_forum(post)

    text = body.body.strip()
    fields: list[dict[str, str]] = []
    if not text or len(text) > 4000:
        fields.append({"field": "body", "message": "Body must be 1–4000 characters."})

    if body.parent_id:
        fields.append({"field": "parent_id", "message": "Comments are on the post. A new floor is not accepted."})

    if fields:
        raise validation_error(fields)

    try:
        comment = create_comment(
            db,
            post_id=post.id,
            author_id=user.id,
            body=text,
            parent_id=None,
        )
    except StorageError:
        raise ApiError(503, "storage_unavailable", "Could not save the comment. Try again in a moment.") from None

    authors = {user.id: user}
    if comment.parent_id:
        return JSONResponse(status_code=201, content=_reply_payload(comment, authors))

    try:
        floor_total = db.scalar(
            select(func.count()).select_from(Comment).where(
                Comment.post_id == post_id,
                Comment.parent_id.is_(None),
            )
        ) or 1
    except SQLAlchemyError as exc:
        raise StorageError() from exc
    return JSONResponse(status_code=201, content=_floor_payload(comment, floor_total, [], authors))


@router.post("/posts/{post_id}/likes")
def like_post(
    post_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_not_muted(user)
    post = _published_post(db, parse_uuid(post_id))
    if post.category != "forum":
        raise validation_error(
            [{"field": "category", "message": "Likes are only available on forum posts."}]
        )
    try:
        created = add_like(db, user_id=user.id, post_id=post.id)
        count = count_likes(db, post.id)
    except StorageError:
        raise ApiError(503, "storage_unavailable", "Could not save the like. Try again in a moment.") from None
    return JSONResponse(
        status_code=201 if created else 200,
        content=LikeState(like_count=count, liked=True).model_dump(),
    )


@router.delete("/posts/{post_id}/likes")
def unlike_post(
    post_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_not_muted(user)
    post = _published_post(db, parse_uuid(post_id))
    if post.category != "forum":
        raise validation_error(
            [{"field": "category", "message": "Likes are only available on forum posts."}]
        )
    try:
        remove_like(db, user_id=user.id, post_id=post.id)
        count = count_likes(db, post.id)
    except StorageError:
        raise ApiError(503, "storage_unavailable", "Could not save the like. Try again in a moment.") from None
    return LikeState(like_count=count, liked=False).model_dump()


@router.post("/posts/{post_id}/images")
async def upload_post_image(
    post_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
):
    require_not_muted(user)
    post = _published_post(db, parse_uuid(post_id))
    if post.author_id != user.id:
        raise forbidden()
    if post.category != "forum":
        raise validation_error(
            [{"field": "category", "message": "Images can only be added to forum posts."}]
        )
    images = parse_images(getattr(post, "images", None))
    if len(images) >= MAX_POST_IMAGES:
        raise validation_error(
            [{"field": "file", "message": "Forum posts can have at most 4 images."}]
        )
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    ext = ALLOWED_TYPES.get(content_type)
    if ext is None:
        raise validation_error(
            [{"field": "file", "message": "Image must be a jpeg, png, or webp file."}]
        )
    data = await file.read()
    if not data or len(data) > MAX_POST_IMAGE_BYTES:
        raise validation_error([{"field": "file", "message": "Image must be 1–2000000 bytes."}])
    try:
        images.append(save_post_image(post.id, ext, data))
        post.images = dump_images(images)
        db.flush()
    except OSError as exc:
        raise StorageError() from exc
    except SQLAlchemyError as exc:
        raise StorageError() from exc
    return _detail(post, author=user)


@router.get("/posts/{post_id}")
def get_post(
    post_id: str,
    db: Session = Depends(get_db),
    core: Session = Depends(get_core_db),
    viewer: User | None = Depends(get_optional_user),
):
    post = _published_post(db, parse_uuid(post_id))
    if post.category == "forum" and viewer is None:
        raise unauthenticated()
    return _public_detail(db, core, post, viewer)


def _public_detail(db: Session, core: Session, post: Post, viewer: User | None):
    blocks = _published_blocks(db, post)
    like_count = count_likes(db, post.id) if post.category == "forum" else 0
    liked = (
        user_liked(db, user_id=viewer.id, post_id=post.id)
        if viewer and post.category == "forum"
        else False
    )
    author = users_by_ids(core, [post.author_id]).get(post.author_id)
    topic_rows = db.scalars(select(NewsCategory).where(NewsCategory.post_id == post.id)).all()
    body = post.body
    if topic_rows:
        article_block = db.scalar(
            select(NewsBlock).where(NewsBlock.post_id == post.id).order_by(NewsBlock.position.asc())
        )
        body = article_block.published_body if article_block else post.body
    return _detail(
        post,
        author=author,
        blocks=blocks,
        like_count=like_count,
        liked=liked,
        news_categories=["scoop" if row.topic == "school" else row.topic for row in topic_rows],
        body=body,
    )


def _image_field_errors(category: str, uploads: list[tuple[str, bytes]]) -> list[dict[str, str]]:
    fields: list[dict[str, str]] = []
    if uploads and category != "forum":
        fields.append({"field": "images", "message": "Images can only be added to forum posts."})
        return fields
    if len(uploads) > MAX_POST_IMAGES:
        fields.append({"field": "images", "message": "Forum posts can have at most 4 images."})
        return fields
    for _ext, data in uploads:
        if not data or len(data) > MAX_POST_IMAGE_BYTES:
            fields.append({"field": "images", "message": "Image must be 1–2000000 bytes."})
            break
    return fields


async def _read_upload_images(items: list) -> tuple[list[tuple[str, bytes]], list[dict[str, str]]]:
    uploads: list[tuple[str, bytes]] = []
    for item in items:
        if not isinstance(item, StarletteUploadFile):
            continue
        content_type = (item.content_type or "").split(";")[0].strip().lower()
        ext = ALLOWED_TYPES.get(content_type)
        if ext is None:
            return [], [{"field": "images", "message": "Image must be a jpeg, png, or webp file."}]
        data = await item.read()
        uploads.append((ext, data))
    return uploads, []


@router.post("/posts", status_code=201)
async def create_post(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    content_type = (request.headers.get("content-type") or "").split(";")[0].strip().lower()
    uploads: list[tuple[str, bytes]] = []
    if content_type == "application/json":
        payload = await request.json()
        if not isinstance(payload, dict):
            raise validation_error([{"field": "title", "message": "Title must be 1–120 characters."}])
        body = CreatePostBody.model_validate(payload)
    elif content_type.startswith("multipart/form-data"):
        form = await request.form()
        body = CreatePostBody(
            title=str(form.get("title") or ""),
            body=str(form.get("body") or ""),
            category=str(form.get("category") or ""),
        )
        uploads, upload_fields = await _read_upload_images(form.getlist("images"))
        if upload_fields:
            raise validation_error(upload_fields)
    else:
        raise validation_error([{"field": "title", "message": "Title must be 1–120 characters."}])

    require_not_muted(user)
    fields = _post_field_errors(body)
    fields.extend(_image_field_errors(body.category, uploads))
    if fields:
        raise validation_error(fields)
    if body.category != "forum":
        raise forbidden("News is published from approved drafts.")

    try:
        post = create_post_with_audit(
            db,
            author_id=user.id,
            title=body.title.strip(),
            body=body.body.strip(),
            category=body.category,
        )
        if uploads:
            paths = [save_post_image(post.id, ext, data) for ext, data in uploads]
            post.images = dump_images(paths)
            db.flush()
    except StorageError:
        delete_post_images(getattr(post, "id", "") if "post" in locals() else "")
        raise ApiError(
            503,
            "storage_unavailable",
            "Could not save the post. Try again in a moment.",
        ) from None
    except OSError as exc:
        if "post" in locals():
            db.rollback()
            delete_post_images(post.id)
        raise StorageError() from exc
    except SQLAlchemyError as exc:
        if "post" in locals():
            delete_post_images(post.id)
        raise StorageError() from exc
    return JSONResponse(status_code=201, content=_detail(post, author=user))


@router.get("/me/posts")
def my_posts(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    core: Session = Depends(get_core_db),
    page: str | None = Query(default=None),
    page_size: str | None = Query(default=None),
):
    parsed_page = parse_page(page)
    parsed_size = parse_page_size(page_size)
    return _list_posts(
        db,
        core,
        page=parsed_page,
        page_size=parsed_size,
        category=None,
        author_id=user.id,
        viewer=user,
    )


@router.delete("/posts/{post_id}", status_code=204)
def delete_post(
    post_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    core: Session = Depends(get_core_db),
):
    post_id = parse_uuid(post_id)
    post = _any_post(db, post_id)
    owns_forum = post.author_id == user.id and post.category == "forum"
    if not owns_forum and not user_has(user, *MODERATOR_ROLES):
        raise forbidden()
    if post.author_id != user.id:
        add_system_notice(core, user_id=post.author_id, body=f'Your post "{post.title}" was removed.')
    delete_post_graph(db, post)
    delete_post_images(post_id)


@router.post("/posts/{post_id}/pin")
def pin_post(
    post_id: str,
    body: PinPostBody,
    user: User = Depends(get_super_admin),
    db: Session = Depends(get_db),
    core: Session = Depends(get_core_db),
):
    post = _any_post(db, parse_uuid(post_id))
    if post.status != "published":
        raise validation_error([{"field": "pinned", "message": "Only a published post can be pinned."}])
    post.pinned = body.pinned
    post.pinned_at = utc_now() if body.pinned else None
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise StorageError() from exc
    db.refresh(post)
    return _public_detail(db, core, post, user)


@router.api_route("/posts/{post_id}/promote", methods=["POST"])
def promote_removed(post_id: str):
    raise StarletteHTTPException(status_code=405)


@router.api_route("/posts/{post_id}", methods=["PATCH"])
def posts_mutating_not_allowed(post_id: str):
    raise StarletteHTTPException(status_code=405)


@router.delete("/posts/{post_id}/comments/{comment_id}", status_code=204)
def withdraw_comment(
    post_id: str,
    comment_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    core: Session = Depends(get_core_db),
):
    post_id = parse_uuid(post_id)
    comment_id = parse_uuid(comment_id, field="comment_id")
    post = _published_post(db, post_id)
    _require_forum(post)
    try:
        comment = db.get(Comment, comment_id)
    except SQLAlchemyError as exc:
        raise StorageError() from exc
    if comment is None or comment.post_id != post.id:
        raise ApiError(404, "not_found", "Comment not found.")
    if comment.author_id != user.id and not user_has(user, *MODERATOR_ROLES):
        raise forbidden()
    if comment.author_id != user.id:
        add_system_notice(
            core,
            user_id=comment.author_id,
            body=f'Your comment on "{post.title}" was removed.',
        )
    delete_comment(db, comment)


@router.api_route("/posts/{post_id}/comments/{comment_id}", methods=["PATCH"])
def comments_mutating_not_allowed(post_id: str, comment_id: str):
    raise StarletteHTTPException(status_code=405)
