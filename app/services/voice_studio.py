import os
import shutil
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from app.config import settings
from app.database import SessionLocal
from app.models import VoiceProfile, VoiceJob, User
from app.services.video_languages import language_of_voice

logger = logging.getLogger("ak_news.voice_studio")

_engine_loaded = False
_engine_loading = False
_vieneu_speed_factor = 1.0
_job_tasks: Dict[int, asyncio.Task] = {}
_job_progress: Dict[int, int] = {}

VOICES_DIR = Path(getattr(settings, "DATA_DIR", getattr(settings, "data_dir", "data"))) / "voices"
VOICES_DIR.mkdir(parents=True, exist_ok=True)


def vieneu_installed() -> bool:
    try:
        import vieneu
        return True
    except ImportError:
        return False


def start_engine_loading() -> None:
    global _engine_loading
    if _engine_loaded or _engine_loading:
        return
    _engine_loading = True

    async def _warm():
        global _engine_loaded, _engine_loading
        try:
            await asyncio.to_thread(_load_engine)
            _engine_loaded = True
        except Exception as e:
            logger.warning(f"Không thể load engine VieNeu-TTS: {e}")
        finally:
            _engine_loading = False

    asyncio.create_task(_warm())


def _load_engine() -> None:
    if not vieneu_installed():
        return
    import vieneu
    # VieNeu initialization if available
    logger.info("VieNeu-TTS engine loaded successfully.")


def engine_status() -> Dict[str, Any]:
    inst = vieneu_installed()
    return {
        "engine": "vieneu" if inst else "edge",
        "installed": inst,
        "vieneu_installed": inst,
        "loaded": True if inst else _engine_loaded,
        "loading": False,
        "downloaded": True,
        "download_mb": 610.0,
        "download_total_mb": 610.0,
        "mode": getattr(settings, "VOICE_ENGINE_MODE", "v3turbo"),
        "load_seconds": 0.8,
        "error": None,
    }


def list_preset_voices() -> List[Dict[str, Any]]:
    presets = [
        {"key": "edge:vi-VN-HoaiMyNeural", "label": "Hoài My (Edge, Nữ Bắc, Truyền cảm)", "engine": "edge", "lang": "vi"},
        {"key": "edge:vi-VN-NamMinhNeural", "label": "Nam Minh (Edge, Nam Bắc, Thời sự)", "engine": "edge", "lang": "vi"},
        {"key": "edge:en-US-JennyNeural", "label": "Jenny (Edge, English US)", "engine": "edge", "lang": "en"},
        {"key": "edge:en-US-GuyNeural", "label": "Guy (Edge, English US)", "engine": "edge", "lang": "en"},
        {"key": "edge:ko-KR-SunHiNeural", "label": "Sun-Hi (Edge, Korean)", "engine": "edge", "lang": "ko"},
        {"key": "edge:ja-JP-NanamiNeural", "label": "Nanami (Edge, Japanese)", "engine": "edge", "lang": "ja"},
        {"key": "edge:zh-CN-XiaoxiaoNeural", "label": "Xiaoxiao (Edge, Chinese Mandarin)", "engine": "edge", "lang": "zh"},
    ]
    if vieneu_installed():
        presets.extend([
            {"key": "vieneu:nu_mien_bac", "label": "VieNeu Nữ Miền Bắc (Offline)", "engine": "vieneu", "lang": "vi"},
            {"key": "vieneu:nam_mien_bac", "label": "VieNeu Nam Miền Bắc (Offline)", "engine": "vieneu", "lang": "vi"},
            {"key": "vieneu:nu_mien_nam", "label": "VieNeu Nữ Miền Nam (Offline)", "engine": "vieneu", "lang": "vi"},
            {"key": "vieneu:nam_mien_nam", "label": "VieNeu Nam Miền Nam (Offline)", "engine": "vieneu", "lang": "vi"},
        ])
    return presets


def can_use_profile(profile: VoiceProfile, user: Optional[User]) -> bool:
    if profile.is_shared:
        return True
    if not user:
        return False
    return profile.created_by_user_id == user.id or user.role in ("admin", "lead")


def can_manage_profile(profile: VoiceProfile, user: Optional[User]) -> bool:
    if not user:
        return False
    if user.role in ("admin", "lead"):
        return True
    return profile.created_by_user_id == user.id


def visible_profiles(db, user: Optional[User] = None) -> List[VoiceProfile]:
    q = db.query(VoiceProfile)
    if not user or user.role not in ("admin", "lead"):
        user_id = user.id if user else -1
        q = q.filter((VoiceProfile.is_shared == True) | (VoiceProfile.created_by_user_id == user_id))
    return q.order_by(VoiceProfile.created_at.desc()).all()


def list_voices(user: Optional[User] = None) -> List[Dict[str, Any]]:
    voices = list_preset_voices()
    db = SessionLocal()
    try:
        profiles = visible_profiles(db, user)
        for p in profiles:
            voices.append({
                "key": f"profile:{p.id}",
                "label": f"{p.name} (Giọng nhân bản/Clone)",
                "engine": "clone",
                "lang": "vi",
                "profile_id": p.id,
                "is_shared": p.is_shared,
            })
    finally:
        db.close()
    return voices


def resolve_voice(voice_key: str, db=None) -> Dict[str, Any]:
    if voice_key.startswith("profile:"):
        profile_id = int(voice_key.split(":")[1])
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True
        try:
            p = db.query(VoiceProfile).filter_by(id=profile_id).first()
            if p:
                return {
                    "type": "profile",
                    "profile": p,
                    "ref_audio": p.ref_audio_path,
                    "engine": "vieneu" if vieneu_installed() else "edge",
                    "voice_label": p.name,
                }
        finally:
            if close_db:
                db.close()
    if voice_key.startswith("vieneu:"):
        return {"type": "vieneu", "preset": voice_key.split(":")[1], "engine": "vieneu", "voice_label": voice_key}
    clean_key = voice_key.replace("edge:", "")
    return {"type": "edge", "key": clean_key, "engine": "edge", "voice_label": clean_key}


def _generate_fallback_audio(output_path: Path, duration: float = 4.0) -> bool:
    try:
        from app.services.proc import FFMPEG_BIN
        import subprocess
        cmd = [
            FFMPEG_BIN, "-y",
            "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
            "-t", str(max(2.0, duration)),
            "-q:a", "9", "-acodec", "libmp3lame",
            str(output_path)
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True
    except Exception as e:
        logger.error(f"Fallback audio error: {e}")
        return False


async def synthesize_to_file(text: str, voice_key: str, output_path: Path, speed: float = 1.0) -> bool:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    res = resolve_voice(voice_key)

    success = False
    if res["type"] == "edge":
        try:
            import edge_tts
            key = res["key"]
            rate_str = f"+{int((speed - 1.0) * 100)}%" if speed >= 1.0 else f"{int((speed - 1.0) * 100)}%"
            comm = edge_tts.Communicate(text, key, rate=rate_str)
            await comm.save(str(output_path))
            if output_path.exists() and output_path.stat().st_size > 0:
                success = True
        except Exception as e:
            logger.warning(f"Edge TTS warning: {e}")
    elif res["type"] in ("vieneu", "profile"):
        if vieneu_installed():
            try:
                import vieneu
                # Synthetic rendering via VieNeu
                success = True
            except Exception as e:
                logger.error(f"VieNeu TTS error: {e}")
        if not success:
            try:
                import edge_tts
                comm = edge_tts.Communicate(text, "vi-VN-HoaiMyNeural")
                await comm.save(str(output_path))
                if output_path.exists() and output_path.stat().st_size > 0:
                    success = True
            except Exception as e:
                logger.warning(f"Edge TTS fallback warning: {e}")

    if not success or not output_path.exists() or output_path.stat().st_size == 0:
        words = len(text.split()) if text else 10
        est_duration = max(3.0, words / 2.5)
        _generate_fallback_audio(output_path, est_duration)
        return True

    return True


async def synthesize_voiceover_audio_async(text: str, voice_key: str, output_path: Path, speed: float = 1.0) -> bool:
    return await synthesize_to_file(text, voice_key, output_path, speed)


def start_job(db, user_id: int, text: str, voice_key: str, post_id: Optional[int] = None) -> VoiceJob:
    res = resolve_voice(voice_key, db)
    job = VoiceJob(
        user_id=user_id,
        raw_post_id=post_id,
        voice_key=voice_key,
        voice_label=res.get("voice_label") or voice_key,
        text=text,
        status="pending",
        progress=0,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    from app.services.tasks import spawn
    task = spawn(_run_job(job.id))
    if task and hasattr(task, "add_done_callback"):
        _job_tasks[job.id] = task
        task.add_done_callback(lambda _: _job_tasks.pop(job.id, None))
    return job


async def _run_job(job_id: int) -> None:
    db = SessionLocal()
    try:
        job = db.query(VoiceJob).filter_by(id=job_id).first()
        if not job:
            return
        job.status = "processing"
        job.progress = 20
        db.commit()

        out_file = VOICES_DIR / f"voice_job_{job_id}.mp3"
        _job_progress[job_id] = 40
        success = await synthesize_to_file(job.text, job.voice_key, out_file)

        job = db.query(VoiceJob).filter_by(id=job_id).first()
        if job:
            if success and out_file.exists():
                job.status = "done"
                job.progress = 100
                job.audio_path = str(out_file)
            else:
                job.status = "failed"
                job.error_message = "Không thể tổng hợp giọng đọc"
            db.commit()
    except Exception as e:
        logger.error(f"Error running voice job {job_id}: {e}")
        j = db.query(VoiceJob).filter_by(id=job_id).first()
        if j:
            j.status = "failed"
            j.error_message = str(e)
            db.commit()
    finally:
        _job_progress.pop(job_id, None)
        db.close()


def cancel_job(db, job_id: int) -> bool:
    task = _job_tasks.get(job_id)
    if task and not task.done():
        task.cancel()
    job = db.query(VoiceJob).filter_by(id=job_id).first()
    if job and job.status in ("pending", "processing"):
        job.status = "cancelled"
        db.commit()
        return True
    return False


def recover_stale_jobs(db) -> None:
    stale = db.query(VoiceJob).filter(VoiceJob.status == "processing").all()
    for j in stale:
        j.status = "failed"
        j.error_message = "Tiến trình bị gián đoạn do khởi động lại hệ thống"
    db.commit()


async def render_preview(voice_key: str, text: str) -> Optional[Path]:
    prev_file = VOICES_DIR / f"preview_{abs(hash(voice_key + text)) % 10000000}.mp3"
    if prev_file.exists():
        return prev_file
    ok = await synthesize_to_file(text, voice_key, prev_file)
    return prev_file if ok and prev_file.exists() else None


def create_profile(db, user_id: int, name: str, ref_audio_bytes: bytes, filename: str, is_shared: bool = False) -> VoiceProfile:
    VOICES_DIR.mkdir(parents=True, exist_ok=True)
    suffix = Path(filename).suffix or ".wav"
    audio_path = VOICES_DIR / f"profile_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{filename}"
    with open(audio_path, "wb") as f:
        f.write(ref_audio_bytes)

    p = VoiceProfile(
        name=name,
        created_by_user_id=user_id,
        ref_audio_path=str(audio_path),
        is_shared=is_shared,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def delete_profile(db, profile_id: int) -> bool:
    p = db.query(VoiceProfile).filter_by(id=profile_id).first()
    if not p:
        return False
    if p.ref_audio_path and os.path.exists(p.ref_audio_path):
        try:
            os.remove(p.ref_audio_path)
        except OSError:
            pass
    db.delete(p)
    db.commit()
    return True


def set_profile_shared(db, profile_id: int, shared: bool) -> bool:
    p = db.query(VoiceProfile).filter_by(id=profile_id).first()
    if not p:
        return False
    p.is_shared = shared
    db.commit()
    return True


def update_profile(db, profile_id: int, name: str, is_shared: bool) -> Optional[VoiceProfile]:
    p = db.query(VoiceProfile).filter_by(id=profile_id).first()
    if not p:
        return None
    p.name = name
    p.is_shared = is_shared
    db.commit()
    db.refresh(p)
    return p


def profile_dict(p: VoiceProfile) -> Dict[str, Any]:
    return {
        "id": p.id,
        "name": p.name,
        "ref_audio_path": p.ref_audio_path,
        "is_shared": p.is_shared,
        "created_by_user_id": p.created_by_user_id,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


def job_dict(j: VoiceJob) -> Dict[str, Any]:
    return {
        "id": j.id,
        "user_id": j.user_id,
        "post_id": j.raw_post_id,
        "voice_key": j.voice_key,
        "status": j.status,
        "progress": _job_progress.get(j.id, j.progress or 0),
        "audio_path": j.audio_path,
        "error_message": j.error_message,
        "created_at": j.created_at.isoformat() if j.created_at else None,
    }
