from pydantic import BaseModel, ConfigDict, Field


NEWSPAPER_CATEGORIES = ("news",)
CATEGORIES = (*NEWSPAPER_CATEGORIES, "forum")
CATEGORY_MESSAGE = "Must be one of: news, forum."
ROLES = ("student", "teacher", "editor", "admin", "super_admin")
NEWSROOM_ROLES = ("editor", "super_admin")
MODERATOR_ROLES = ("admin", "super_admin")
ASSIGNABLE_ROLES = ("student", "teacher", "editor", "admin")
CJ_VIEWER_ROLES = ("student", "teacher", "super_admin")
CJ_EDITOR_ROLES = ("super_admin",)
REVIEW_STATUSES = ("editing", "pending", "published")
AVATAR_PRESETS = ("oak", "gym", "book", "dorm", "bus", "night")
DEFAULT_AVATAR = "preset:oak"


class RegisterBody(BaseModel):
    email: str
    password: str
    display_name: str
    code: str
    accept_terms: bool


class LoginBody(BaseModel):
    email: str
    password: str


class EmailCodeBody(BaseModel):
    email: str
    purpose: str


class PasswordResetBody(BaseModel):
    email: str
    code: str
    password: str


class ChangePasswordBody(BaseModel):
    current_password: str
    password: str


class BottleTextBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    body: str


class CreatePostBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str
    body: str
    category: str


class SetAvatarPresetBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    preset: str


class AuthorPublic(BaseModel):
    id: str
    display_name: str
    avatar: str
    is_agent: bool = False


class UserPrivate(BaseModel):
    id: str
    email: str
    display_name: str
    roles: list[str]
    avatar: str
    muted: bool
    terms_accepted_at: str | None
    created_at: str


class ReplyPreview(BaseModel):
    id: str
    body: str
    created_at: str
    author: AuthorPublic


class CreateCommentBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    body: str
    parent_id: str | None = None


class PatchUserRoleBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    roles: list[str] | None = None
    muted: bool | None = None


class CreateDraftBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str


class CreateBlockBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    heading: str
    body: str
    position: int | None = None


class PatchBlockBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    heading: str | None = None
    body: str | None = None


class CommentReply(BaseModel):
    id: str
    body: str
    parent_id: str
    created_at: str
    author: AuthorPublic


class CommentFloor(BaseModel):
    id: str
    body: str
    parent_id: None
    floor: int
    created_at: str
    author: AuthorPublic
    replies: list[CommentReply]


class CommentList(BaseModel):
    items: list[CommentFloor]
    page: int
    page_size: int
    total: int


class UserList(BaseModel):
    items: list[UserPrivate]
    page: int
    page_size: int
    total: int


class PostSummary(BaseModel):
    id: str
    title: str
    excerpt: str
    category: str
    status: str
    created_at: str
    updated_at: str
    author: AuthorPublic
    reply_count: int
    reply_preview: list[ReplyPreview]
    images: list[str]
    news_categories: list[str] = Field(default_factory=list)
    like_count: int
    liked: bool
    pinned: bool = False


class PublishedBlock(BaseModel):
    id: str
    heading: str
    body: str
    position: int


class PostDetail(PostSummary):
    body: str
    blocks: list[PublishedBlock] = []


class PinPostBody(BaseModel):
    pinned: bool


class Notice(BaseModel):
    id: str
    body: str
    created_at: str


class NoticeList(BaseModel):
    items: list[Notice]


class NewsBlockStaff(BaseModel):
    id: str
    position: int
    heading: str
    draft_body: str
    published_heading: str | None
    published_body: str | None
    review_status: str


class NewsDraftSummary(BaseModel):
    id: str
    title: str
    status: str
    created_at: str
    updated_at: str
    author: AuthorPublic


class NewsDraftDetail(NewsDraftSummary):
    blocks: list[NewsBlockStaff]


class NewsDraftList(BaseModel):
    items: list[NewsDraftSummary]
    page: int
    page_size: int
    total: int


class PatchNewsSubmissionBody(BaseModel):
    title: str | None = None
    body: str | None = None
    topics: list[str] | None = None


class RemoveNewsSubmissionImageBody(BaseModel):
    image: str


class PublishNewsSubmissionBody(BaseModel):
    mode: str = "formatted"


class LikeState(BaseModel):
    like_count: int
    liked: bool


class ForumActivity(BaseModel):
    unread: int


class PostList(BaseModel):
    items: list[PostSummary]
    page: int
    page_size: int
    total: int
