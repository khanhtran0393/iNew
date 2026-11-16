import os
import asyncio
from starlette.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models import User, RawPost, MediaItem, MediaType, PublishTarget

def run_deep_routes_audit():
    print("=" * 70)
    print("   KIỂM TOÁN CHUYÊN SÂU TẤT CẢ CÁC API ENDPOINTS NGHIỆP VỤ")
    print("=" * 70)

    db = SessionLocal()
    post = db.query(RawPost).first()
    media_item = db.query(MediaItem).first()
    if not media_item and post:
        media_item = MediaItem(
            raw_post_id=post.id,
            media_type=MediaType.PHOTO,
            file_path="app/web/static/img/icon-256.png",
            file_name="icon-256.png"
        )
        db.add(media_item)
        db.commit()
        db.refresh(media_item)
    target = db.query(PublishTarget).first()
    if not target:
        target = PublishTarget(platform="youtube", name="Default Youtube", target_id="yt_1", is_active=True)
        db.add(target)
        db.commit()
        db.refresh(target)

    post_id = post.id if post else 1
    media_id = media_item.id if media_item else 1
    target_id = target.id if target else 1
    db.close()

    client = TestClient(app)
    # Login properly to get inew_session cookie
    login_resp = client.post("/auth/login", data={"username": "admin", "password": "admin123456"}, follow_redirects=False)
    session_cookie = login_resp.cookies.get("inew_session")
    assert session_cookie, "Không lấy được session cookie!"
    client.cookies.set("inew_session", session_cookie)
    print(f"  [✓] Đăng nhập thành công! Session cookie: {session_cookie[:25]}...")

    test_endpoints = [
        ("POST", "/api/ai/action", {"action": "summarize", "text": "Test tin tuc iNew"}),
        ("POST", "/api/ai-assist", {"action": "title", "post_id": post_id}),
        ("GET", f"/api/posts/{post_id}/ai-history", None),
        ("POST", f"/api/posts/{post_id}/fetch-article", {}),
        ("POST", f"/posts/{post_id}/assign", {"assignee_id": 1, "notes": "Auditing"}),
        ("POST", f"/posts/{post_id}/edit", {"edited_text": "Updated editorial text"}),
        ("POST", f"/api/ai-media", {"post_id": post_id, "media_item_id": media_id, "action": "image_describe"}),
        ("GET", f"/api/posts/{post_id}/ai-media-history", None),
        ("POST", "/api/video-editor/script", {"post_id": post_id}),
        ("GET", "/api/publish-targets", None),
        ("POST", "/api/publish-video", {"post_id": post_id, "video_rel_path": "final_outputs/post_1/video_1.mp4", "target_ids": [target_id]}),
        ("GET", "/api/studio/assets", None),
        ("GET", "/api/studio/templates", None),
        ("POST", "/api/studio/ai-image/suggest", {"text": "Chính phủ ban hành chính sách công nghệ cao"}),
        ("GET", "/settings/api/ai-models", None),
        ("GET", "/api/voice/status", None),
        ("GET", "/api/voice/profiles", None),
        ("POST", "/api/voice/jobs", {"voice_key": "edge:vi-VN-HoaiMyNeural", "text": "Test giọng đọc", "post_id": post_id}),
        ("GET", "/api/lipsync/avatars", None),
        ("POST", "/maintenance/run", {}),
        ("POST", "/settings/system/lan", {"allow_lan": True}),
        ("POST", "/settings/system/check-update", {}),
    ]

    passed = 0
    failed = 0

    for method, path, payload in test_endpoints:
        try:
            if method == "GET":
                resp = client.get(path, follow_redirects=True)
            elif method == "POST":
                # For form post redirects or json
                if path.startswith("/posts/") or path in ("/maintenance/run", "/settings/system/lan", "/settings/system/check-update"):
                    resp = client.post(path, data=payload if payload is not None else {}, follow_redirects=True)
                else:
                    resp = client.post(path, json=payload if payload is not None else {}, follow_redirects=True)
            
            # Check 200 or 201 or 204
            if resp.status_code in (200, 201, 204):
                print(f"  [✓] {method:<4} {path:<38} -> {resp.status_code} OK (Data length: {len(resp.content)} bytes)")
                passed += 1
            else:
                print(f"  [✗] {method:<4} {path:<38} -> {resp.status_code} ({resp.text[:80]})")
                failed += 1
        except Exception as e:
            print(f"  [ERROR] {method:<4} {path:<38} -> Exception: {e}")
            failed += 1

    print("=" * 70)
    print(f"  KẾT QUẢ: {passed} PASSED, {failed} FAILED (Tổng: {len(test_endpoints)})")
    print("=" * 70)
    assert failed == 0, f"{failed} endpoints failed!"

if __name__ == "__main__":
    run_deep_routes_audit()
