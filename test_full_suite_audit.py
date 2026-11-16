import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

os.environ["FASTAPI_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///data/ak_news.db"

import importlib
from starlette.testclient import TestClient

print("=" * 70)
print("     EXHAUSTIVE 68-MODULE DECOMPILATION & RECONSTRUCTION AUDIT")
print("=" * 70)

MODULES = [
    # Core Root Modules
    "app._build_info",
    "app.benchmark_report",
    "app.config",
    "app.database",
    "app.init_db",
    "app.launcher",
    "app.main",
    "app.models",
    "app.resources",
    "app.telegram_login",

    # Services (Business Logic & Daemons)
    "app.services.ai_copilot",
    "app.services.ai_image",
    "app.services.ai_key_router",
    "app.services.ai_media",
    "app.services.article_fetcher",
    "app.services.auto_video_service",
    "app.services.backup_service",
    "app.services.benchmark_service",
    "app.services.bulk_import",
    "app.services.deduplication",
    "app.services.desktop",
    "app.services.diagnostics",
    "app.services.editorial_workflow",
    "app.services.licensing",
    "app.services.lipsync_service",
    "app.services.llm_providers",
    "app.services.maintenance_service",
    "app.services.media_fetcher",
    "app.services.media_storage",
    "app.services.multi_platform_publisher",
    "app.services.outbox_dispatcher",
    "app.services.proc",
    "app.services.rss_collector",
    "app.services.runtime_config",
    "app.services.security_crypto",
    "app.services.source_admin",
    "app.services.staff_notify",
    "app.services.studio_store",
    "app.services.tasks",
    "app.services.telegram_bot",
    "app.services.telegram_ingestion",
    "app.services.telegram_web_collector",
    "app.services.updates",
    "app.services.video_editor_service",
    "app.services.video_languages",
    "app.services.video_producer",
    "app.services.video_remixer",
    "app.services.voice_studio",
    "app.services.web_news_collector",

    # Web & Routes
    "app.web.auth",
    "app.web.templating",
    "app.web.routes.api_routes",
    "app.web.routes.audit",
    "app.web.routes.auth_routes",
    "app.web.routes.benchmark",
    "app.web.routes.dashboard",
    "app.web.routes.license_routes",
    "app.web.routes.lipsync",
    "app.web.routes.posts",
    "app.web.routes.settings_routes",
    "app.web.routes.setup_routes",
    "app.web.routes.sources",
    "app.web.routes.studio",
    "app.web.routes.system_routes",
    "app.web.routes.topics",
    "app.web.routes.users",
    "app.web.routes.videos",
    "app.web.routes.voice",
]

print("[*] 1. IMPORT TEST FOR ALL 68 MODULES:")
failed = []
for mod in MODULES:
    try:
        importlib.import_module(mod)
        print(f"  [✓] {mod}")
    except Exception as e:
        print(f"  [✗] FAILED: {mod} -> {e}")
        failed.append((mod, str(e)))

print("\n[*] 2. SUMMARY OF MODULE IMPORTS:")
if not failed:
    print(f"  ==> 100% PERFECT! ALL {len(MODULES)}/{len(MODULES)} MODULES IMPORTED WITH 0 ERRORS!")
else:
    print(f"  ==> {len(failed)} modules failed.")
    sys.exit(1)

print("\n[*] 3. HTTP ENDPOINT LIVE RESPONSE VERIFICATION:")
from app.main import app
client = TestClient(app)

endpoints = [
    ("/health/live", 200),
    ("/health/ready", 200),
    ("/setup", 200),
    ("/license", 200),
    ("/auth/login", 200),
]

for ep, expected_code in endpoints:
    resp = client.get(ep)
    print(f"  [✓] GET {ep:16s} -> {resp.status_code} (Expected {expected_code})")
    assert resp.status_code == expected_code, f"Unexpected code {resp.status_code} for {ep}"

print("\n[*] 4. AUTHENTICATED ENDPOINTS VERIFICATION:")
login_resp = client.post("/auth/login", data={"username": "admin", "password": "admin123456"}, follow_redirects=False)
cookie = login_resp.cookies.get("inew_session")
assert cookie, "Login failed to produce session cookie"
print(f"  [✓] Login OK! Session cookie generated.")

auth_endpoints = [
    ("/dashboard", 200),
    ("/feed", 200),
    ("/posts", 200),
    ("/posts/1", 200),
    ("/topics", 200),
    ("/users", 200),
    ("/users/change-password", 200),
    ("/videos", 200),
    ("/voice", 200),
    ("/sources", 200),
    ("/benchmark", 200),
    ("/audit", 200),
    ("/settings/ai", 200),
    ("/settings/telegram", 200),
    ("/settings/system", 200),
    ("/system/settings", 200),
    ("/editor/video", 200),
    ("/help", 200),
    ("/support", 200),
    ("/support/diagnostics.zip", 200),
]

for ep, expected_code in auth_endpoints:
    resp = client.get(ep, cookies={"inew_session": cookie})
    print(f"  [✓] GET {ep:25s} -> {resp.status_code} (Length: {len(resp.content):6d} bytes)")
    assert resp.status_code == expected_code, f"Unexpected code {resp.status_code} for {ep}"

print("=" * 70)
print("     ALL 68 MODULES & ALL 25 ROUTE VIEWS VERIFIED 100% OPERATIONAL!")
print("=" * 70)
