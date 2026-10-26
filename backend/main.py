import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from avatars import ensure_avatar_dir
from cj_sync import run_scheduled_sync
from config import load_settings
from errors import register_exception_handlers
from models import init_content_db, init_core_db, make_engine, make_session_factory
from routers.admin import router as admin_router
from routers.auth import router as auth_router
from routers.bell import router as bell_router
from routers.bottles import router as bottles_router
from routers.games import router as games_router
from routers.cj import router as cj_router
from routers.news import router as news_router
from routers.news_articles import router as news_articles_router
from routers.posts import router as posts_router
from games.chess_rooms import router as chess_room_router
from games.gomoku_rooms import router as gomoku_room_router


logger = logging.getLogger("elegram.cj")
_SYNC_INTERVAL_SECONDS = 3600
_SYNC_START_DELAY_SECONDS = 5


async def _cj_sync_loop(app: FastAPI) -> None:
    await asyncio.sleep(_SYNC_START_DELAY_SECONDS)
    while True:
        try:
            await asyncio.to_thread(run_scheduled_sync, app)
        except Exception:
            logger.exception("CJ journal sync failed")
        await asyncio.sleep(_SYNC_INTERVAL_SECONDS)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    task = None
    if app.state.settings.cj_journal_base_url:
        task = asyncio.create_task(_cj_sync_loop(app))
    try:
        yield
    finally:
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task


def create_app() -> FastAPI:
    settings = load_settings()
    shared_database = settings.database_url == settings.core_database_url
    if shared_database:
        core_engine = content_engine = make_engine(settings.database_url)
    else:
        core_engine = make_engine(settings.core_database_url)
        content_engine = make_engine(settings.database_url)
    init_core_db(core_engine)
    init_content_db(content_engine)

    app = FastAPI(title="Elegram API", lifespan=_lifespan)
    app.state.settings = settings
    app.state.shared_database = shared_database
    app.state.core_engine = core_engine
    app.state.content_engine = content_engine
    app.state.core_session_factory = make_session_factory(core_engine)
    app.state.content_session_factory = make_session_factory(content_engine)
    # Backwards-compatible aliases: the content store is the default session.
    app.state.engine = content_engine
    app.state.session_factory = app.state.content_session_factory

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(posts_router, prefix="/api/v1")
    app.include_router(bell_router, prefix="/api/v1")
    app.include_router(bottles_router, prefix="/api/v1")
    app.include_router(games_router, prefix="/api/v1")
    app.include_router(gomoku_room_router)
    app.include_router(chess_room_router)
    app.include_router(cj_router, prefix="/api/v1")
    app.include_router(news_router, prefix="/api/v1")
    app.include_router(news_articles_router, prefix="/api/v1")
    app.include_router(admin_router, prefix="/api/v1")
    app.mount("/uploads", StaticFiles(directory=str(ensure_avatar_dir().parent)), name="uploads")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


_app: FastAPI | None = None


def __getattr__(name: str):
    global _app
    if name == "app":
        if _app is None:
            _app = create_app()
        return _app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
