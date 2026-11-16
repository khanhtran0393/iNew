"""FastAPI Application Entrypoint, Lifespan orchestration, and Router bindings."""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, JSONResponse

from app.config import settings
from app.init_db import init_db
from app.services.runtime_config import apply_saved_config, ensure_setup_flag
from app.services.voice_studio import recover_stale_jobs, start_engine_loading
from app.services.licensing import evaluate_state, license_enforced

# Import Background workers
from app.services.outbox_dispatcher import outbox_worker_loop
from app.services.rss_collector import sync_all_vietnamese_news_feeds
from app.services.auto_video_service import auto_video_worker_loop
from app.services.backup_service import backup_worker_loop
from app.services.telegram_web_collector import telegram_web_worker_loop
from app.services.maintenance_service import maintenance_worker_loop
from app.services.benchmark_service import benchmark_worker_loop
from app.services.article_fetcher import article_worker_loop
from app.services.web_news_collector import web_news_worker_loop
from app.services.licensing import license_checkin_loop
from app.services.updates import check_loop

# Import Routers
from app.web.routes.auth_routes import router as auth_router
from app.web.routes.dashboard import router as dashboard_router
from app.web.routes.posts import router as posts_router
from app.web.routes.sources import router as sources_router
from app.web.routes.topics import router as topics_router
from app.web.routes.users import router as users_router
from app.web.routes.settings_routes import router as settings_router
from app.web.routes.videos import router as videos_router
from app.web.routes.voice import router as voice_router
from app.web.routes.lipsync import router as lipsync_router
from app.web.routes.audit import router as audit_router
from app.web.routes.benchmark import router as benchmark_router
from app.web.routes.license_routes import router as license_router
from app.web.routes.setup_routes import router as setup_router
from app.web.routes.system_routes import router as system_router
from app.web.routes.api_routes import router as api_router

logger = logging.getLogger("ak_news.main")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

_background_tasks = []


async def rss_sync_worker_loop():
    while True:
        try:
            sync_all_vietnamese_news_feeds(limit_per_feed=15)
            await asyncio.sleep(600)
        except Exception as e:
            logger.error(f"Error in RSS sync worker: {e}")
            await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}...")
    init_db()
    applied = apply_saved_config()
    if applied:
        logger.info(f"Applied web-configured settings: {', '.join(applied)}")

    recover_stale_jobs()
    start_engine_loading()

    # Start Background Workers
    workers = [
        outbox_worker_loop,
        rss_sync_worker_loop,
        auto_video_worker_loop,
        backup_worker_loop,
        telegram_web_worker_loop,
        maintenance_worker_loop,
        benchmark_worker_loop,
        article_worker_loop,
        web_news_worker_loop,
        license_checkin_loop,
        check_loop,
    ]
    for w in workers:
        task = asyncio.create_task(w())
        _background_tasks.append(task)

    yield

    logger.info("Shutting down iNew...")
    for task in _background_tasks:
        task.cancel()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan
)

# License Gate Middleware (Universal Portable Shield)
PUBLIC_WHEN_LOCKED = ["/license", "/static", "/logout"]


@app.middleware("http")
async def license_gate(request: Request, call_next):
    if license_enforced():
        state = evaluate_state()
        if state.get("locked"):
            path = request.url.path
            if not any(path.startswith(p) for p in PUBLIC_WHEN_LOCKED):
                if path.startswith("/api/"):
                    return JSONResponse({"detail": "Phần mềm chưa kích hoạt bản quyền"}, status_code=403)
                return RedirectResponse(url="/license")
    return await call_next(request)


# Mount Static Files
static_dir = Path(__file__).resolve().parent / "web" / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Mount Media Files
app.mount("/media/raw", StaticFiles(directory=str(settings.raw_media_dir)), name="raw_media")
app.mount("/media/edited", StaticFiles(directory=str(settings.edited_media_dir)), name="edited_media")

# Include Routers
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(posts_router)
app.include_router(sources_router)
app.include_router(topics_router)
app.include_router(users_router)
app.include_router(settings_router)
app.include_router(videos_router)
app.include_router(voice_router)
app.include_router(lipsync_router)
app.include_router(audit_router)
app.include_router(benchmark_router)
app.include_router(license_router)
app.include_router(setup_router)
app.include_router(system_router)
app.include_router(api_router)
