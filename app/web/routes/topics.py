import re
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Topic, User, EditorialGroup
from app.web.templating import templates
from app.web.auth import get_current_user, require_roles, require_admin

router = APIRouter(prefix="", tags=["topics"])


@router.get("/topics")
def topics_view(
    request: Request,
    notice: str = "",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    topics = db.query(Topic).order_by(Topic.name.asc()).all()
    groups = db.query(EditorialGroup).order_by(EditorialGroup.id.asc()).all()
    return templates.TemplateResponse(
        "topics.html",
        {
            "request": request,
            "current_user": user,
            "topics": topics,
            "groups": groups,
            "notice": notice,
        }
    )


@router.post("/topics/create")
def create_topic(
    name: str = Form(...),
    slug: str = Form(""),
    keywords: str = Form(""),
    user: User = Depends(require_roles(["admin", "lead"])),
    db: Session = Depends(get_db)
):
    clean_name = name.strip()
    clean_slug = slug.strip().lower()
    if not clean_slug:
        clean_slug = re.sub(r"[^a-z0-9]+", "-", clean_name.lower()).strip("-")

    existing = db.query(Topic).filter((Topic.name == clean_name) | (Topic.slug == clean_slug)).first()
    if not existing:
        topic = Topic(name=clean_name, slug=clean_slug, keywords=keywords.strip())
        db.add(topic)
        db.commit()
    return RedirectResponse(url="/topics", status_code=303)


@router.post("/topics/delete/{topic_id}")
@router.post("/topics/{topic_id}/delete")
def delete_topic(
    topic_id: int,
    user: User = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db)
):
    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if topic:
        db.delete(topic)
        db.commit()
    return RedirectResponse(url="/topics", status_code=303)


# Editorial Groups Handlers
@router.post("/editorial-groups/create")
def create_editorial_group(
    title: str = Form(...),
    telegram_chat_id: int = Form(...),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    grp = EditorialGroup(
        title=title.strip(),
        telegram_chat_id=telegram_chat_id,
        is_active=True
    )
    db.add(grp)
    db.commit()
    return RedirectResponse(url="/topics", status_code=303)


@router.post("/editorial-groups/{grp_id}/toggle")
def toggle_editorial_group(grp_id: int, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    grp = db.query(EditorialGroup).filter_by(id=grp_id).first()
    if grp:
        grp.is_active = not grp.is_active
        db.commit()
    return RedirectResponse(url="/topics", status_code=303)


@router.post("/editorial-groups/{grp_id}/delete")
def delete_editorial_group(grp_id: int, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    grp = db.query(EditorialGroup).filter_by(id=grp_id).first()
    if grp:
        db.delete(grp)
        db.commit()
    return RedirectResponse(url="/topics", status_code=303)


@router.post("/editorial-groups/{grp_id}/test")
async def test_editorial_group(grp_id: int, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    grp = db.query(EditorialGroup).filter_by(id=grp_id).first()
    if grp and grp.telegram_chat_id:
        from app.services.telegram_bot import send_telegram_message
        await send_telegram_message(
            grp.telegram_chat_id,
            f"🔔 <b>Thông báo thử nghiệm từ iNew</b>\nNhóm biên tập <b>{grp.title}</b> đã kết nối thành công!"
        )
    return RedirectResponse(url="/topics", status_code=303)
