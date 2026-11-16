import json
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode
from fastapi import APIRouter, Request, Depends, Form, Query, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import RawPost, SourceChannel, Topic, User, WorkflowStatus, RawPostStatus, GeneratedVideo, PublishTarget, WorkflowAuditLog, VoiceJob, RawPostEditHistory
from app.web.templating import templates
from app.web.auth import get_current_user
from app.services.editorial_workflow import claim_post_atomic, update_post_status

router = APIRouter(prefix="", tags=["posts"])


@router.get("/my_posts")
def my_posts_shortcut():
    return RedirectResponse(url="/posts?assignee=me&status=active", status_code=303)


@router.get("/feed")
@router.get("/posts")
def news_feed_view(
    request: Request,
    page: int = Query(1),
    assignee: str = Query(""),
    status: str = Query(""),
    source_id: str = Query(""),
    media: str = Query(""),
    q: str = Query(""),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(RawPost)

    if assignee == "me":
        query = query.filter(RawPost.assigned_to == user.id)
    if status and status != "all":
        query = query.filter(RawPost.status == status)
    if source_id and source_id.isdigit():
        query = query.filter(RawPost.source_channel_id == int(source_id))
    if q.strip():
        query = query.filter(RawPost.title.contains(q.strip()) | RawPost.original_text.contains(q.strip()))

    total = query.count()
    limit = 25
    offset = max(0, (page - 1) * limit)
    posts = query.order_by(RawPost.created_at.desc()).offset(offset).limit(limit).all()

    f = {
        "assignee": assignee,
        "status": status,
        "source_id": source_id,
        "media": media,
        "q": q,
        "date_from": "",
        "date_to": "",
    }

    def page_qs(target_page: int) -> str:
        params = {k: v for k, v in f.items() if v}
        params["page"] = str(target_page)
        return "?" + urlencode(params)

    status_labels = {
        "new": "Tin Mới",
        "duplicate": "Trùng Lặp",
        "ready": "Sẵn Sàng",
        "claimed": "Đã Nhận",
        "editing": "Đang Biên Tập",
        "approved": "Đã Duyệt",
        "completed": "Hoàn Thành",
        "archived": "Lưu Trữ",
    }

    sources = db.query(SourceChannel).filter(SourceChannel.is_active == True).all()
    topics = db.query(Topic).all()
    users = db.query(User).filter(User.is_active == True).all()

    return templates.TemplateResponse("feed.html", {
        "request": request,
        "current_user": user,
        "posts": posts,
        "total": total,
        "page": page,
        "page_qs": page_qs,
        "f": f,
        "status_labels": status_labels,
        "sources": sources,
        "topics": topics,
        "users": users,
    })


@router.get("/posts/{post_id}")
def post_detail_view(
    post_id: int,
    request: Request,
    msg: Optional[str] = Query(None),
    err: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    post = db.query(RawPost).filter(RawPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài viết")

    publish_targets = db.query(PublishTarget).filter_by(is_active=True).all()
    latest_video = db.query(GeneratedVideo).filter_by(raw_post_id=post_id, status="ready").order_by(GeneratedVideo.id.desc()).first()
    latest_script = None
    if latest_video and latest_video.script_json:
        try:
            latest_script = json.loads(latest_video.script_json)
        except Exception:
            pass

    last_feedback = db.query(WorkflowAuditLog).filter_by(raw_post_id=post_id).order_by(WorkflowAuditLog.id.desc()).first()
    staff = db.query(User).filter_by(is_active=True).all()
    voice_jobs = db.query(VoiceJob).filter_by(raw_post_id=post_id).order_by(VoiceJob.id.desc()).all()

    is_owner = (post.assigned_to == user.id)
    can_work = is_owner or (user.role in ("admin", "lead"))

    voice_audio_rel = ""
    voice_file = None
    if latest_video and latest_video.file_path and Path(latest_video.file_path).exists():
        voice_file = latest_video.file_path
        voice_audio_rel = Path(latest_video.file_path).name

    user_role_slug = getattr(user.role, "slug", str(user.role)) if user.role else "editor"
    is_admin = (user_role_slug == "admin")
    is_lead = (user_role_slug in ("admin", "lead"))
    can_edit = can_work
    can_approve = is_lead
    can_assign = is_lead

    status_labels = {
        "new": "Tin Mới",
        "duplicate": "Trùng Lặp",
        "ready": "Sẵn Sàng",
        "claimed": "Đã Nhận",
        "verifying": "Đang Xác Minh",
        "editing": "Đang Biên Tập",
        "reviewing": "Chờ Duyệt",
        "pending_review": "Chờ Duyệt",
        "approved": "Đã Duyệt",
        "rejected": "Bác Bỏ",
        "skipped": "Bỏ Qua",
        "completed": "Hoàn Thành",
        "archived": "Lưu Trữ",
    }

    ai_media = [m for m in (post.media_items or []) if m.media_type in ("image", "video", "photo")]

    from app.services.ai_media import MEDIA_AI_ACTIONS
    media_ai_actions = {
        k: {
            "label": v.get("title", k),
            "media": v["media_type"].value if hasattr(v["media_type"], "value") else str(v["media_type"]),
            "title": v.get("title", k)
        }
        for k, v in MEDIA_AI_ACTIONS.items()
    }

    return templates.TemplateResponse("post_detail.html", {
        "request": request,
        "current_user": user,
        "post": post,
        "status_labels": status_labels,
        "can_approve": can_approve,
        "can_assign": can_assign,
        "can_edit": can_edit,
        "can_work": can_work,
        "is_owner": is_owner,
        "is_admin": is_admin,
        "flash_msg": msg,
        "flash_err": err,
        "ai_media": ai_media,
        "media_ai_actions": media_ai_actions,
        "msg": msg,
        "err": err,
        "publish_targets": publish_targets,
        "latest_video": latest_video,
        "latest_script": latest_script,
        "last_feedback": last_feedback,
        "staff": staff,
        "voice_jobs": voice_jobs,
        "voice_audio_rel": voice_audio_rel,
        "voice_file": voice_file,
    })


@router.post("/posts/{post_id}/claim")
def claim_post_action(post_id: int, user: User = Depends(get_current_user)):
    claim_post_atomic(post_id, user.id)
    return RedirectResponse(url=f"/posts/{post_id}", status_code=303)


@router.post("/posts/{post_id}/status")
def update_status_action(post_id: int, status: str = Form(...), user: User = Depends(get_current_user)):
    update_post_status(post_id, status, user_id=user.id)
    return RedirectResponse(url=f"/posts/{post_id}", status_code=303)


@router.post("/posts/{post_id}/assign")
def assign_post_action(
    post_id: int,
    assignee_id: int = Form(...),
    notes: Optional[str] = Form(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    post = db.query(RawPost).filter(RawPost.id == post_id).first()
    if post:
        post.assigned_user_id = assignee_id
        if post.workflow_status in (WorkflowStatus.CLAIMED.value, "new"):
            post.workflow_status = WorkflowStatus.CLAIMED.value
        if notes:
            post.editorial_notes = (post.editorial_notes or "") + f"\n[Giao việc bởi {user.username}]: {notes}"

        audit = WorkflowAuditLog(
            raw_post_id=post_id,
            user_id=user.id,
            action=f"assigned_to_user_{assignee_id}",
            note=notes or ""
        )
        db.add(audit)
        db.commit()
    return RedirectResponse(url=f"/posts/{post_id}", status_code=303)


@router.post("/posts/{post_id}/edit")
@router.post("/posts/{post_id}/save")
def save_edited_text_action(
    post_id: int,
    edited_text: Optional[str] = Form(""),
    editorial_notes: Optional[str] = Form(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    post = db.query(RawPost).filter(RawPost.id == post_id).first()
    if post:
        old_text = post.edited_text
        if edited_text is not None:
            post.edited_text = edited_text
        if editorial_notes is not None:
            post.editorial_notes = editorial_notes

        if old_text != edited_text:
            hist = RawPostEditHistory(
                raw_post_id=post_id,
                user_id=user.id,
                old_text=old_text,
                new_text=edited_text or ""
            )
            db.add(hist)
        db.commit()
    return RedirectResponse(url=f"/posts/{post_id}", status_code=303)
