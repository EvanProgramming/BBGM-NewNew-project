import json
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def to_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


class CoreBase(DeclarativeBase):
    """CJ student database: users, sessions, subjects, exams, CJ entries, Teams."""


class ContentBase(DeclarativeBase):
    """News and sharing database: posts, news blocks, comments, likes, audit."""


# ---------------------------------------------------------------------------
# Core (CJ student) tables
# ---------------------------------------------------------------------------


class User(CoreBase):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(String(40), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="student")
    roles: Mapped[str] = mapped_column(Text, nullable=False, default='["student"]')
    avatar: Mapped[str] = mapped_column(String(160), nullable=False, default="preset:oak")
    muted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    terms_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    sessions: Mapped[list["SessionRecord"]] = relationship(back_populates="user")


class SessionRecord(CoreBase):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped[User] = relationship(back_populates="sessions")


class SystemNotice(CoreBase):
    __tablename__ = "system_notices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Subject(CoreBase):
    __tablename__ = "subjects"
    __table_args__ = (UniqueConstraint("name", name="idx_subjects_name"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    short_name: Mapped[str] = mapped_column(String(40), nullable=False)
    color: Mapped[str] = mapped_column(String(16), nullable=False)
    period: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    grade: Mapped[int] = mapped_column(Integer, nullable=False, default=11)
    class_section: Mapped[str] = mapped_column(String(16), nullable=False, default="All")
    teacher: Mapped[str] = mapped_column(String(120), nullable=False, default="To be confirmed")
    room: Mapped[str] = mapped_column(String(80), nullable=False, default="To be confirmed")
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_custom: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class CJTeacherSubject(CoreBase):
    __tablename__ = "cj_teacher_subjects"
    __table_args__ = (
        UniqueConstraint("user_id", "subject_id", name="uq_cj_teacher_subject"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.id"), nullable=False)


class Exam(CoreBase):
    __tablename__ = "exams"
    __table_args__ = (Index("idx_exams_week_day", "week_start", "day_index"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    week_start: Mapped[str] = mapped_column(String(10), nullable=False)
    day_index: Mapped[int] = mapped_column(Integer, nullable=False)
    subject_id: Mapped[str | None] = mapped_column(ForeignKey("subjects.id"), nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    time: Mapped[str] = mapped_column(String(5), nullable=False)
    location: Mapped[str] = mapped_column(Text, nullable=False, default="")
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)


class CJEntry(CoreBase):
    __tablename__ = "cj_entries"
    __table_args__ = (
        UniqueConstraint(
            "week_start",
            "day_index",
            "period",
            "subject_id",
            name="idx_cj_entry_slot",
        ),
        Index("idx_cj_entries_week_day", "week_start", "day_index"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    week_start: Mapped[str] = mapped_column(String(10), nullable=False)
    day_index: Mapped[int] = mapped_column(Integer, nullable=False)
    period: Mapped[int] = mapped_column(Integer, nullable=False)
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.id"), nullable=False)
    ic: Mapped[str] = mapped_column(Text, nullable=False, default="")
    hw: Mapped[str] = mapped_column(Text, nullable=False, default="")
    announcement: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)


class TeamsConnection(CoreBase):
    __tablename__ = "teams_connections"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    refresh_token: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)


class TeamsOAuthState(CoreBase):
    __tablename__ = "teams_oauth_states"

    state: Mapped[str] = mapped_column(String(80), primary_key=True)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)


class EmailCode(CoreBase):
    __tablename__ = "email_codes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    purpose: Mapped[str] = mapped_column(String(16), nullable=False)
    code_hash: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


# ---------------------------------------------------------------------------
# Content (news & sharing) tables
#
# `author_id` / `user_id` / `actor_id` reference users that live in the CJ
# database (a different MySQL database), so they are plain indexed columns:
# MySQL cannot enforce a foreign key across databases. The application loads
# the referenced users from the core database when it serializes content.
# ---------------------------------------------------------------------------


class Post(ContentBase):
    __tablename__ = "posts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    author_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    excerpt: Mapped[str] = mapped_column(String(160), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    is_activity: Mapped[bool] = mapped_column(Boolean, nullable=False)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    images: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    comments: Mapped[list["Comment"]] = relationship(back_populates="post")
    likes: Mapped[list["PostLike"]] = relationship(back_populates="post")
    blocks: Mapped[list["NewsBlock"]] = relationship(back_populates="post")


class NewsBlock(ContentBase):
    __tablename__ = "news_blocks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    post_id: Mapped[str] = mapped_column(ForeignKey("posts.id"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    heading: Mapped[str] = mapped_column(String(120), nullable=False)
    published_heading: Mapped[str | None] = mapped_column(String(120), nullable=True)
    draft_body: Mapped[str] = mapped_column(Text, nullable=False)
    formatted_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    format_source: Mapped[str | None] = mapped_column(String(16), nullable=True)
    published_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    post: Mapped[Post] = relationship(back_populates="blocks")


class NewsCategory(ContentBase):
    __tablename__ = "news_categories"
    __table_args__ = (UniqueConstraint("post_id", "topic", name="uq_news_categories_post_topic"),)

    post_id: Mapped[str] = mapped_column(ForeignKey("posts.id"), primary_key=True)
    topic: Mapped[str] = mapped_column(String(16), primary_key=True)


class Comment(ContentBase):
    __tablename__ = "comments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    post_id: Mapped[str] = mapped_column(ForeignKey("posts.id"), nullable=False)
    author_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("comments.id"), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    post: Mapped[Post] = relationship(back_populates="comments")


class PostLike(ContentBase):
    __tablename__ = "post_likes"
    __table_args__ = (UniqueConstraint("user_id", "post_id", name="uq_post_likes_user_post"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    post_id: Mapped[str] = mapped_column(ForeignKey("posts.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    post: Mapped[Post] = relationship(back_populates="likes")


class AuditEvent(ContentBase):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    post_id: Mapped[str] = mapped_column(ForeignKey("posts.id"), nullable=False)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


def make_engine(database_url: str):
    connect_args = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        # Seconds another connection may wait when this file is already being written.
        connect_args["timeout"] = 30
    engine = create_engine(database_url, connect_args=connect_args)
    if database_url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _sqlite_wal(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

    return engine


def make_session_factory(engine):
    return sessionmaker(bind=engine, expire_on_commit=False)


def _sqlite_drop_users_banned(conn) -> None:
    conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
    conn.exec_driver_sql(
        """
        CREATE TABLE users__new (
            id VARCHAR(36) NOT NULL PRIMARY KEY,
            email VARCHAR(320) NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            display_name VARCHAR(40) NOT NULL,
            role VARCHAR(16) NOT NULL DEFAULT 'student',
            avatar VARCHAR(160) NOT NULL DEFAULT 'preset:oak',
            muted INTEGER NOT NULL DEFAULT 0,
            terms_accepted_at DATETIME,
            created_at DATETIME NOT NULL
        )
        """
    )
    conn.exec_driver_sql(
        """
        INSERT INTO users__new (
            id, email, password_hash, display_name, role, avatar, muted, terms_accepted_at, created_at
        )
        SELECT id, email, password_hash, display_name, role, avatar,
               COALESCE(muted, banned, 0), terms_accepted_at, created_at
        FROM users
        """
    )
    conn.exec_driver_sql("DROP TABLE users")
    conn.exec_driver_sql("ALTER TABLE users__new RENAME TO users")
    conn.exec_driver_sql("PRAGMA foreign_keys=ON")


def _drop_sports_and_backfill_blocks(conn) -> None:
    sports_ids = [
        row[0] for row in conn.exec_driver_sql("SELECT id FROM posts WHERE category='sports'").fetchall()
    ]
    if sports_ids:
        marks = ",".join("?" for _ in sports_ids)
        for sql in (
            f"DELETE FROM comments WHERE post_id IN ({marks})",
            f"DELETE FROM post_likes WHERE post_id IN ({marks})",
            f"DELETE FROM audit_events WHERE post_id IN ({marks})",
            f"DELETE FROM news_blocks WHERE post_id IN ({marks})",
            f"DELETE FROM posts WHERE id IN ({marks})",
        ):
            conn.exec_driver_sql(sql, sports_ids)
    rows = conn.exec_driver_sql(
        """
        SELECT p.id, p.title, p.body, p.created_at
        FROM posts p
        WHERE p.category = 'news'
          AND NOT EXISTS (SELECT 1 FROM news_blocks b WHERE b.post_id = p.id)
        """
    ).fetchall()
    for post_id, title, body, created_at in rows:
        heading = ((title or "Story").strip() or "Story")[:120]
        text = body or ""
        conn.exec_driver_sql(
            """
            INSERT INTO news_blocks (
                id, post_id, position, heading, published_heading,
                draft_body, published_body, review_status, created_at, updated_at
            ) VALUES (?, ?, 1, ?, ?, ?, ?, 'published', ?, ?)
            """,
            (str(uuid4()), post_id, heading, heading, text, text, created_at, created_at),
        )


def migrate_core_schema(engine) -> None:
    if engine.dialect.name == "sqlite":
        with engine.begin() as conn:
            cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(users)").fetchall()}
            if cols and "role" not in cols:
                conn.exec_driver_sql(
                    "ALTER TABLE users ADD COLUMN role VARCHAR(16) NOT NULL DEFAULT 'student'"
                )
            if cols and "avatar" not in cols:
                conn.exec_driver_sql(
                    "ALTER TABLE users ADD COLUMN avatar VARCHAR(160) NOT NULL DEFAULT 'preset:oak'"
                )
            if cols and "muted" not in cols:
                conn.exec_driver_sql(
                    "ALTER TABLE users ADD COLUMN muted INTEGER NOT NULL DEFAULT 0"
                )
                if "banned" in cols:
                    conn.exec_driver_sql("UPDATE users SET muted = banned")
            if cols and "terms_accepted_at" not in cols:
                conn.exec_driver_sql("ALTER TABLE users ADD COLUMN terms_accepted_at DATETIME")
            cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(users)").fetchall()}
            if cols and "banned" in cols:
                _sqlite_drop_users_banned(conn)
            cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(users)").fetchall()}
            if cols and "roles" not in cols:
                conn.exec_driver_sql(
                    "ALTER TABLE users ADD COLUMN roles TEXT NOT NULL DEFAULT '[\"student\"]'"
                )
                for user_id, role in conn.exec_driver_sql("SELECT id, role FROM users").fetchall():
                    stored = json.dumps([role] if role in {
                        "student", "teacher", "editor", "admin", "super_admin"
                    } else ["student"])
                    conn.exec_driver_sql(
                        "UPDATE users SET roles = ? WHERE id = ?",
                        (stored, user_id),
                    )
            subject_cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(subjects)").fetchall()}
            subject_columns = {
                "grade": "INTEGER NOT NULL DEFAULT 11",
                "class_section": "VARCHAR(16) NOT NULL DEFAULT 'All'",
                "teacher": "VARCHAR(120) NOT NULL DEFAULT 'To be confirmed'",
                "room": "VARCHAR(80) NOT NULL DEFAULT 'To be confirmed'",
                "required": "INTEGER NOT NULL DEFAULT 0",
                "is_custom": "INTEGER NOT NULL DEFAULT 0",
            }
            for column, definition in subject_columns.items():
                if subject_cols and column not in subject_cols:
                    conn.exec_driver_sql(f"ALTER TABLE subjects ADD COLUMN {column} {definition}")
    CoreBase.metadata.create_all(engine)
    if engine.dialect.name == "sqlite":
        with engine.begin() as conn:
            tables = {
                row[0]
                for row in conn.exec_driver_sql(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            if "exams" in tables:
                exam_cols = {
                    row[1] for row in conn.exec_driver_sql("PRAGMA table_info(exams)").fetchall()
                }
                if "subject_id" not in exam_cols:
                    conn.exec_driver_sql("ALTER TABLE exams ADD COLUMN subject_id VARCHAR(64)")
                conn.exec_driver_sql(
                    "UPDATE exams SET subject_id='ap-calculus' "
                    "WHERE subject_id IS NULL AND title LIKE 'AP Calculus AB%'")
                conn.exec_driver_sql(
                    "UPDATE exams SET subject_id='ap-economics' "
                    "WHERE subject_id IS NULL AND title LIKE 'AP Economics%'")


def migrate_content_schema(engine) -> None:
    if engine.dialect.name == "sqlite":
        with engine.begin() as conn:
            post_cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(posts)").fetchall()}
            if post_cols and "images" not in post_cols:
                conn.exec_driver_sql(
                    "ALTER TABLE posts ADD COLUMN images TEXT NOT NULL DEFAULT '[]'"
                )
            block_cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(news_blocks)").fetchall()}
            if block_cols and "formatted_body" not in block_cols:
                conn.exec_driver_sql("ALTER TABLE news_blocks ADD COLUMN formatted_body TEXT")
            if block_cols and "format_source" not in block_cols:
                conn.exec_driver_sql("ALTER TABLE news_blocks ADD COLUMN format_source VARCHAR(16)")
    ContentBase.metadata.create_all(engine)
    if engine.dialect.name == "sqlite":
        with engine.begin() as conn:
            tables = {
                row[0]
                for row in conn.exec_driver_sql(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            if "posts" in tables:
                conn.exec_driver_sql("UPDATE posts SET category='forum' WHERE category='community'")
                conn.exec_driver_sql("UPDATE posts SET category='news' WHERE category='dorm_life'")
                conn.exec_driver_sql("UPDATE posts SET category='news' WHERE category='events'")
                conn.exec_driver_sql(
                    "UPDATE posts SET is_activity=0, starts_at=NULL, location=NULL "
                    "WHERE is_activity != 0 OR starts_at IS NOT NULL OR location IS NOT NULL"
                )
                _drop_sports_and_backfill_blocks(conn)


def init_core_db(engine) -> None:
    migrate_core_schema(engine)


def init_content_db(engine) -> None:
    migrate_content_schema(engine)
