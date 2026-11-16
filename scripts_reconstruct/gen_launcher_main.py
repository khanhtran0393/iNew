import os
from pathlib import Path

app_dir = Path("app")

# 1. app/launcher.py
launcher_code = '''import os
import sys
import time
import socket
import asyncio
import webbrowser
import threading
from pathlib import Path
from PIL import Image
import uvicorn
from app.config import settings


def _port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) == 0


def _open_browser_when_ready(url: str, port: int) -> None:
    for _ in range(50):
        time.sleep(0.2)
        if _port_in_use(port):
            webbrowser.open(url)
            break


def _make_tray(stop_event: threading.Event):
    try:
        import pystray
        tray_img_path = Path("app/web/static/img/tray.png")
        if not tray_img_path.is_file():
            img = Image.new("RGBA", (64, 64), color=(34, 158, 217, 255))
        else:
            img = Image.open(tray_img_path)

        def on_open(icon, item):
            webbrowser.open(f"http://127.0.0.1:{settings.PORT}")

        def on_exit(icon, item):
            icon.stop()
            stop_event.set()
            os._exit(0)

        menu = pystray.Menu(
            pystray.MenuItem("Mở iNew", on_open, default=True),
            pystray.MenuItem("Thoát", on_exit)
        )
        icon = pystray.Icon("iNew", img, "iNew - Tin tức đa nền tảng", menu)
        icon.run()
    except Exception as e:
        print(f"Tray icon warning: {e}")


def _prepare_environment() -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.raw_media_dir.mkdir(parents=True, exist_ok=True)
    settings.edited_media_dir.mkdir(parents=True, exist_ok=True)
    settings.backup_dir.mkdir(parents=True, exist_ok=True)
    settings.final_outputs_dir.mkdir(parents=True, exist_ok=True)
    settings.voices_dir.mkdir(parents=True, exist_ok=True)
    settings.lipsync_dir.mkdir(parents=True, exist_ok=True)
    settings.avatars_dir.mkdir(parents=True, exist_ok=True)


def serve() -> None:
    _prepare_environment()
    url = f"http://127.0.0.1:{settings.PORT}"
    threading.Thread(target=_open_browser_when_ready, args=(url, settings.PORT), daemon=True).start()

    stop_event = threading.Event()
    if os.name == "nt":
        threading.Thread(target=_make_tray, args=(stop_event,), daemon=True).start()

    config = uvicorn.Config(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        log_level="info",
        reload=settings.DEBUG
    )
    server = uvicorn.Server(config)
    server.run()


if __name__ == "__main__":
    serve()
'''

(app_dir / "launcher.py").write_text(launcher_code, encoding="utf-8")

# 2. app/main.py
main_code = '''import os
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from app.config import settings
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
        except Exception as e:
            logger.error(f"Error in outbox dispatcher: {e}")
        await asyncio.sleep(5)


async def rss_sync_worker_loop():
    logger.info("RSS Mainstream News Collector background worker started.")
    while True:
        try:
            from app.services.rss_collector import sync_all_rss_sources
            await asyncio.to_thread(sync_all_rss_sources)
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
    
    # Launch background worker tasks
    t1 = asyncio.create_task(outbox_worker_loop())
    t2 = asyncio.create_task(rss_sync_worker_loop())
    t3 = asyncio.create_task(start_bot())
    _background_tasks.extend([t1, t2, t3])
    
    yield
    
    # Shutdown
    for t in _background_tasks:
        t.cancel()
    logger.info("Shutdown completed.")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    lifespan=lifespan
)

# Static assets mount
static_dir = Path("app/web/static")
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
'''

(app_dir / "main.py").write_text(main_code, encoding="utf-8")
print("Generated launcher.py and main.py")
