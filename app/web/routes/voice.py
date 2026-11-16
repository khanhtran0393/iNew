from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Request, Depends, HTTPException, UploadFile, File, Form, Body
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, VoiceProfile, VoiceJob
from app.web.templating import templates
from app.web.auth import get_current_user
from app.services.video_languages import choices as video_languages, default_voice_for
from app.services import voice_studio

router = APIRouter(prefix="", tags=["voice"])


@router.get("/voice")
def voice_studio_view(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    voices = voice_studio.list_voices(user)
    profiles = voice_studio.visible_profiles(db, user)
    engine_stat = voice_studio.engine_status()

    return templates.TemplateResponse(
        "voice.html",
        {
            "request": request,
            "current_user": user,
            "voices": voices,
            "default_voice": default_voice_for("vi"),
            "video_languages": video_languages,
            "ref_min": 3,
            "ref_max": 15,
            "max_chars": 5000,
            "retention_days": 30,
            "profiles": [voice_studio.profile_dict(p) for p in profiles],
            "sample_script": "Chào mừng bạn đến với hệ thống xuất bản tin tức đa nền tảng iNew.",
            "engine": engine_stat["engine"],
            "engine_status": engine_stat,
        }
    )


@router.get("/api/voice/status")
def voice_status():
    return voice_studio.engine_status()


@router.post("/api/voice/engine/load")
def voice_engine_load():
    voice_studio.start_engine_loading()
    return {"ok": True, "message": "Đang khởi tạo engine VieNeu-TTS"}


@router.post("/api/voice/jobs")
async def voice_job_start(
    text: str = Body(..., embed=True),
    voice_key: str = Body(..., embed=True),
    post_id: Optional[int] = Body(None, embed=True),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    job = voice_studio.start_job(db, user.id, text, voice_key, post_id)
    return {"ok": True, "job": voice_studio.job_dict(job), "job_id": job.id}


def _own_job(job_id: int, user: User, db: Session) -> VoiceJob:
    job = db.query(VoiceJob).filter_by(id=job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Không tìm thấy tác vụ giọng nói")
    if job.user_id != user.id and user.role not in ("admin", "lead"):
        raise HTTPException(status_code=403, detail="Bạn không có quyền truy cập tác vụ này")
    return job


@router.get("/api/voice/jobs/{job_id}")
def voice_job_status(job_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = _own_job(job_id, user, db)
    return {"ok": True, "job": voice_studio.job_dict(job)}


@router.get("/api/voice/jobs/{job_id}/audio")
def voice_job_audio(job_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = _own_job(job_id, user, db)
    if job.status != "done" or not job.audio_path or not Path(job.audio_path).exists():
        raise HTTPException(status_code=404, detail="File audio chưa sẵn sàng")
    return FileResponse(job.audio_path, media_type="audio/mpeg", filename=f"voice_{job_id}.mp3")


@router.post("/api/voice/jobs/{job_id}/cancel")
def voice_job_cancel(job_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _own_job(job_id, user, db)
    ok = voice_studio.cancel_job(db, job_id)
    return {"ok": ok}


@router.delete("/api/voice/jobs/{job_id}/delete")
def voice_job_delete(job_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = _own_job(job_id, user, db)
    if job.audio_path and Path(job.audio_path).exists():
        try:
            Path(job.audio_path).unlink()
        except OSError:
            pass
    db.delete(job)
    db.commit()
    return {"ok": True}


@router.post("/api/voice/preview")
async def voice_preview(voice_key: str = Body(..., embed=True), text: str = Body(..., embed=True)):
    path = await voice_studio.render_preview(voice_key, text)
    if not path or not path.exists():
        raise HTTPException(status_code=500, detail="Không thể tạo preview giọng đọc")
    return FileResponse(str(path), media_type="audio/mpeg")


@router.get("/api/voice/profiles")
def voice_profiles_list(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profiles = voice_studio.visible_profiles(db, user)
    return {"ok": True, "profiles": [voice_studio.profile_dict(p) for p in profiles]}


@router.post("/api/voice/profiles")
async def voice_profile_create(
    name: str = Form(...),
    is_shared: bool = Form(False),
    audio: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    content = await audio.read()
    if len(content) < 1000:
        raise HTTPException(status_code=400, detail="File mẫu giọng quá ngắn hoặc không hợp lệ")
    p = voice_studio.create_profile(db, user.id, name, content, audio.filename or "sample.wav", is_shared)
    return {"ok": True, "profile": voice_studio.profile_dict(p)}


@router.get("/api/voice/profiles/{profile_id}/sample")
def voice_profile_sample(profile_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.query(VoiceProfile).filter_by(id=profile_id).first()
    if not p or not voice_studio.can_use_profile(p, user):
        raise HTTPException(status_code=404, detail="Không tìm thấy mẫu giọng")
    if not p.ref_audio_path or not Path(p.ref_audio_path).exists():
        raise HTTPException(status_code=404, detail="File mẫu âm thanh không tồn tại")
    return FileResponse(p.ref_audio_path)


@router.delete("/api/voice/profiles/{profile_id}/delete")
def voice_profile_delete(profile_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.query(VoiceProfile).filter_by(id=profile_id).first()
    if not p or not voice_studio.can_manage_profile(p, user):
        raise HTTPException(status_code=403, detail="Không có quyền xóa hồ sơ này")
    ok = voice_studio.delete_profile(db, profile_id)
    return {"ok": ok}


@router.post("/api/voice/profiles/{profile_id}/share")
def voice_profile_share(profile_id: int, shared: bool = Body(..., embed=True), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.query(VoiceProfile).filter_by(id=profile_id).first()
    if not p or not voice_studio.can_manage_profile(p, user):
        raise HTTPException(status_code=403, detail="Không có quyền thay đổi chia sẻ")
    ok = voice_studio.set_profile_shared(db, profile_id, shared)
    return {"ok": ok}


@router.post("/api/voice/profiles/{profile_id}/update")
def voice_profile_update(profile_id: int, name: str = Body(..., embed=True), is_shared: bool = Body(False, embed=True), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.query(VoiceProfile).filter_by(id=profile_id).first()
    if not p or not voice_studio.can_manage_profile(p, user):
        raise HTTPException(status_code=403, detail="Không có quyền cập nhật")
    updated = voice_studio.update_profile(db, profile_id, name, is_shared)
    return {"ok": True, "profile": voice_studio.profile_dict(updated) if updated else None}


@router.post("/api/voice/profiles/{profile_id}/test")
def voice_profile_test(profile_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.query(VoiceProfile).filter_by(id=profile_id).first()
    if not p or not voice_studio.can_use_profile(p, user):
        raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ")
    job = voice_studio.start_job(db, user.id, "Đây là bản thử nghiệm giọng đọc nhân bản.", f"profile:{profile_id}")
    return {"ok": True, "job_id": job.id}


@router.post("/api/voice/default")
def voice_set_default(voice_key: str = Body(..., embed=True), user: User = Depends(get_current_user)):
    res = voice_studio.resolve_voice(voice_key)
    return {"ok": True, "default_voice": res}
