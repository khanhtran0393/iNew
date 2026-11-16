import os
import asyncio
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from app.config import settings
from app.resources import get_asset_path
from app.init_db import init_db
from app.services.licensing import evaluate_state, license_enforced
from app.services.tasks import spawn

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("inew")

_background_tasks = []


async def outbox_worker_loop():
    logger.info("Outbox Dispatcher background worker started.")
    while True:
        try:
            from app.services.telegram_bot import dispatch_pending_outbox
            await dispatch_pending_outbox()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in outbox dispatcher: {e}")
        await asyncio.sleep(5)


async def rss_sync_worker_loop():
    logger.info("RSS Mainstream News Collector background worker started.")
    while True:
        try:
            from app.services.rss_collector import sync_all_rss_sources
            await asyncio.to_thread(sync_all_rss_sources)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in RSS sync worker: {e}")
        await asyncio.sleep(300)


async def start_bot():
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.info("Chưa có token bot. Bỏ qua khởi động Telegram Bot.")
        return
    try:
        from aiogram import Bot, Dispatcher
        from app.services.telegram_bot import setup_bot_handlers
        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        dp = Dispatcher()
        setup_bot_handlers(dp)
        me = await bot.get_me()
        logger.info(f"Telegram Editorial Bot @{me.username} polling started.")
        asyncio.create_task(dp.start_polling(bot, handle_signals=False))
    except Exception as e:
        logger.error(f"Failed to start Telegram Bot: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info(f"Starting {settings.APP_NAME} v{settings.VERSION}...")
    init_db()
    from app.services.runtime_config import apply_saved_config
    apply_saved_config()

    # Core background tasks
    _background_tasks.append(asyncio.create_task(outbox_worker_loop()))
    _background_tasks.append(asyncio.create_task(rss_sync_worker_loop()))
    _background_tasks.append(asyncio.create_task(start_bot()))

    # Launch automated backend daemon workers
    try:
        from app.services.backup_service import backup_worker_loop
        _background_tasks.append(asyncio.create_task(backup_worker_loop()))
        logger.info("Automated SQLite Gzip backup worker loop initialized.")
    except Exception as e:
        logger.warning(f"Could not initialize backup worker: {e}")

    try:
        from app.services.benchmark_service import benchmark_worker_loop
        _background_tasks.append(asyncio.create_task(benchmark_worker_loop()))
        logger.info("Benchmark telemetry worker loop initialized.")
    except Exception as e:
        logger.warning(f"Could not initialize benchmark worker: {e}")

    try:
        from app.services.maintenance_service import maintenance_worker_loop
        _background_tasks.append(asyncio.create_task(maintenance_worker_loop()))
        logger.info("Automated disk & storage maintenance worker loop initialized.")
    except Exception as e:
        logger.warning(f"Could not initialize maintenance worker: {e}")

    try:
        from app.services.article_fetcher import article_worker_loop
        _background_tasks.append(asyncio.create_task(article_worker_loop()))
        logger.info("Automated Trafilatura article extractor loop initialized.")
    except Exception as e:
        logger.warning(f"Could not initialize article extractor worker: {e}")

    try:
        from app.services.auto_video_service import auto_video_worker_loop
        _background_tasks.append(asyncio.create_task(auto_video_worker_loop()))
        logger.info("Automated video production scheduler loop initialized.")
    except Exception as e:
        logger.warning(f"Could not initialize auto video worker: {e}")

    try:
        from app.services.telegram_web_collector import telegram_web_worker_loop
        _background_tasks.append(asyncio.create_task(telegram_web_worker_loop()))
        logger.info("Public Telegram web channel collector loop initialized.")
    except Exception as e:
        logger.warning(f"Could not initialize telegram web worker: {e}")

    try:
        from app.services.web_news_collector import web_news_worker_loop
        _background_tasks.append(asyncio.create_task(web_news_worker_loop()))
        logger.info("Automated newspaper web news crawler worker loop initialized.")
    except Exception as e:
        logger.warning(f"Could not initialize web news worker: {e}")

    try:
        from app.services.telegram_ingestion import ingestion_service
        asyncio.create_task(ingestion_service.start())
        logger.info("Telegram MTProto live ingestion service initialized.")
    except Exception as e:
        logger.warning(f"Could not initialize telegram ingestion service: {e}")

    yield

    # Shutdown
    for t in _background_tasks:
        t.cancel()
    try:
        from app.services.telegram_ingestion import ingestion_service
        await ingestion_service.stop()
    except Exception:
        pass
    logger.info("Shutdown completed.")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    lifespan=lifespan
)

# Static assets mount
static_dir = get_asset_path("app/web/static")
if static_dir.is_dir():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.middleware("http")
async def license_gate(request: Request, call_next):
    path = request.url.path
    # Exempt endpoints
    exempt_prefixes = (
        "/license", "/static", "/auth/login", "/auth/logout",
        "/setup", "/health", "/docs", "/openapi.json"
    )
    if any(path.startswith(p) for p in exempt_prefixes):
        return await call_next(request)

    if license_enforced():
        state = evaluate_state()
        if not state.get("licensed"):
            return RedirectResponse(url="/license", status_code=303)

    return await call_next(request)


@app.exception_handler(HTTPException)
async def http_exception_redirect_handler(request: Request, exc: HTTPException):
    if exc.status_code in (401, 403):
        return RedirectResponse(url="/auth/login", status_code=303)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.get("/")
def root_redirect():
    from app.services.runtime_config import setup_completed
    if not setup_completed():
        return RedirectResponse(url="/setup", status_code=303)
    return RedirectResponse(url="/dashboard", status_code=303)


@app.get("/health/live")
def health_live():
    return {"status": "ok"}


@app.get("/health/ready")
def health_ready():
    return {"status": "ready"}


# Import and register routers
def _include_routes():
    from app.web.routes.auth_routes import router as auth_router
    from app.web.routes.dashboard import router as dashboard_router
    from app.web.routes.posts import router as posts_router
    from app.web.routes.sources import router as sources_router
    from app.web.routes.license_routes import router as license_router
    from app.web.routes.settings_routes import router as settings_router
    from app.web.routes.api_routes import router as api_router
    from app.web.routes.voice import router as voice_router
    from app.web.routes.videos import router as videos_router
    from app.web.routes.lipsync import router as lipsync_router
    from app.web.routes.studio import router as studio_router
    from app.web.routes.users import router as users_router
    from app.web.routes.topics import router as topics_router
    from app.web.routes.audit import router as audit_router
    from app.web.routes.benchmark import router as benchmark_router
    from app.web.routes.setup_routes import router as setup_router
    from app.web.routes.system_routes import router as system_router

    app.include_router(auth_router)
    app.include_router(dashboard_router)
    app.include_router(posts_router)
    app.include_router(sources_router)
    app.include_router(license_router)
    app.include_router(settings_router)
    app.include_router(api_router)
    app.include_router(voice_router)
    app.include_router(videos_router)
    app.include_router(lipsync_router)
    app.include_router(studio_router)
    app.include_router(users_router)
    app.include_router(topics_router)
    app.include_router(audit_router)
    app.include_router(benchmark_router)
    app.include_router(setup_router)
    app.include_router(system_router)

try:
    _include_routes()
except Exception as e:
    logger.warning(f"Deferred router inclusion: {e}")
