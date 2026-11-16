"""News feeds and detailed editorial post manipulation."""

from fastapi import APIRouter, Request, Depends, HTTPException, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, RawPost, WorkflowStatus, Topic
from app.web.auth import get_current_user, require_editor
from app.web.templating import templates
from app.services.editorial_workflow import transition_post_workflow

router = APIRouter(prefix="/posts", tags=["posts"])


@router.get("", response_class=HTMLResponse)
@router.get("/feed", response_class=HTMLResponse)
async def feed_page(
    request: Request,
    workflow: str = "all",
    page: int = 1,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    q = db.query(RawPost)
    if workflow != "all":
        q = q.filter(RawPost.workflow_status == workflow)
    total = q.count()
    posts = q.order_by(RawPost.id.desc()).offset((page - 1) * 20).limit(20).all()

    return templates.TemplateResponse("feed.html", {
        "request": request,
        "user": user,
        "posts": posts,
        "workflow": workflow,
        "page": page,
        "total": total
    })


@router.get("/{post_id}", response_class=HTMLResponse)
async def post_detail_page(post_id: int, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    post = db.query(RawPost).filter(RawPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Bài viết không tồn tại.")
    topics = db.query(Topic).all()
    return templates.TemplateResponse("post_detail.html", {
        "request": request,
        "user": user,
        "post": post,
        "topics": topics
    })


@router.post("/{post_id}/status")
async def update_post_status(
    post_id: int,
    to_status: str = Form(...),
    notes: str = Form(""),
    user: User = Depends(require_editor),
    db: Session = Depends(get_db)
):
    post = db.query(RawPost).filter(RawPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Bài viết không tồn tại.")
    transition_post_workflow(db, post, WorkflowStatus(to_status), user.id, notes)
    return RedirectResponse(url=f"/posts/{post_id}", status_code=status.HTTP_302_FOUND)
