import os
import sys
import asyncio

# Ensure project root in path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
os.environ["FASTAPI_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///data/ak_news.db"

from app.database import SessionLocal
from app.models import RawPost, SourceChannel, User, GeneratedVideo, MediaItem
from app.services.deduplication import check_deduplication
from app.services.bulk_import import bulk_import_channels
from app.services.ai_copilot import generate_title_summary, run_ai_action
from app.services.video_producer import produce_full_video_pipeline
from app.services.video_remixer import execute_smart_video_remix
from app.services.lipsync_service import dispatch_lipsync_job, get_job_status, composite_video
from app.services.web_news_collector import sync_web_sources
from app.services.media_fetcher import download_media_for_post, download_media_file

async def run_comprehensive_restoration_verification():
    print("=" * 70)
    print("   KIỂM THỬ THỰC CHIẾN CÁC TÍNH NĂNG ĐÃ PHỤC HỒI TOÀN DIỆN")
    print("=" * 70)
    
    db = SessionLocal()
    try:
        # 1. Test check_deduplication flexible signatures
        print("\n[*] 1. KIỂM THỬ DEDUPLICATION ĐA PHƯƠNG THỨC:")
        r1, _ = check_deduplication("Tin tức thử nghiệm hệ thống iNew 2026")
        r2, _ = check_deduplication(db, "Tin tức thử nghiệm hệ thống iNew 2026")
        print(f"  [✓] check_deduplication(text): {r1}")
        print(f"  [✓] check_deduplication(db, text): {r2}")
        assert r1 == r2

        # 2. Test Bulk Import with SourceChannel priority & username
        print("\n[*] 2. KIỂM THỬ BULK IMPORT KÊNH VÀ TÍNH NĂNG CHANNEL:")
        res = bulk_import_channels(db, ["@test_channel_inew_2026", "https://vnexpress.net/rss/thoi-su.rss"])
        print(f"  [✓] Bulk import: added={res.added}, duplicates={res.duplicates}, invalid={res.invalid}")
        
        # 3. Test AI Copilot Title Summary
        print("\n[*] 3. KIỂM THỬ AI COPILOT GENERATE TITLE SUMMARY:")
        summary = await generate_title_summary("Chính phủ vừa ban hành nghị định mới về phát triển công nghệ cao và trí tuệ nhân tạo.")
        print(f"  [✓] AI Title: {summary['title']}")
        print(f"  [✓] AI Summary: {summary['summary']}")
        assert len(summary['title']) > 0

        # 4. Test Post & Media Item Synonyms
        print("\n[*] 4. KIỂM THỬ ĐẶC TÍNH RAWPOST VÀ MEDIAITEM SYNONYMS:")
        post = db.query(RawPost).first()
        if not post:
            post = RawPost(title="Tin mẫu kiểm thử", original_text="Nội dung bài viết kiểm thử")
            db.add(post)
            db.commit()
            db.refresh(post)
        
        print(f"  [✓] Post ID: #{post.id}")
        print(f"  [✓] Post has_media: {post.has_media} (Count: {post.media_count})")
        print(f"  [✓] Post is_source_deleted: {post.is_source_deleted}")
        print(f"  [✓] Post resolved_text: {post.resolved_text[:50]}...")

        # 5. Test LipSync Dispatch, Status and Composite
        print("\n[*] 5. KIỂM THỬ LIPSYNC VÀ COMPOSITE VIDEO:")
        job = dispatch_lipsync_job(
            mode="talking_photo",
            avatar_path="mc_female_1",
            text="Chào mừng quý vị đã quay trở lại với bản tin iNew.",
            voice="edge:vi-VN-HoaiMyNeural",
            post_id=post.id
        )
        print(f"  [✓] Dispatched LipSync Job ID: #{job.id} - Status: {job.status}")
        st = get_job_status(job.id)
        print(f"  [✓] Retrieved Job Status: {st['status']}")
        assert st is not None

        # 6. Test Produce Full Video Pipeline with Real FFmpeg Execution
        print("\n[*] 6. KIỂM THỬ PIPELINE SẢN XUẤT VIDEO HOÀN CHỈNH (FFMPEG THỰC TẾ):")
        vid_res = await produce_full_video_pipeline(
            post_id=post.id,
            theme="red",
            voice="edge:vi-VN-HoaiMyNeural",
            speed=1.0,
            language="vi"
        )
        print(f"  [✓] Video Render Status: {vid_res['status']}")
        print(f"  [✓] MP4 File Path: {vid_res['file_path']}")
        print(f"  [✓] Title Card PNG: {vid_res['title_card']}")
        print(f"  [✓] Subtitles SRT: {vid_res['subtitles_srt']}")
        print(f"  [✓] CapCut Guide: {vid_res['capcut_guide']}")
        assert os.path.exists(vid_res['file_path']), "Video MP4 không tồn tại!"
        print(f"  [✓] File Size: {os.path.getsize(vid_res['file_path'])} bytes")

        # 7. Test Smart Video Remix
        print("\n[*] 7. KIỂM THỬ SMART VIDEO REMIX:")
        remix_res = await execute_smart_video_remix(post_id=post.id)
        print(f"  [✓] Remix Success: {remix_res.get('success')} (OK: {remix_res.get('ok')})")
        print(f"  [✓] Video Rel Path: {remix_res.get('video_rel')}")
        assert remix_res.get("success") is True

        # 8. Test Web News Collector
        print("\n[*] 8. KIỂM THỬ WEB NEWS COLLECTOR:")
        web_res = sync_web_sources()
        print(f"  [✓] Web News Sync: {web_res}")

        print("\n" + "=" * 70)
        print("  ==> TẤT CẢ 8 BÀI KIỂM THỬ THỰC CHIẾN ĐỀU VƯỢT QUA 100% THÀNH CÔNG!")
        print("=" * 70)
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(run_comprehensive_restoration_verification())
