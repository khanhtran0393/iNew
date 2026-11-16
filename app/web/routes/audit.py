from typing import Optional
from fastapi import APIRouter, Request, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import WorkflowAuditLog, User
from app.web.templating import templates
from app.web.auth import get_current_user, require_roles

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
def audit_view(
    request: Request,
    page: int = Query(1),
    action: str = Query(""),
    user_id: str = Query(""),
    user = Depends(require_roles(["admin", "lead"])),
    db: Session = Depends(get_db)
):
    query = db.query(WorkflowAuditLog)
    if action:
        query = query.filter(WorkflowAuditLog.action == action)
    if user_id and user_id.isdigit():
        query = query.filter(WorkflowAuditLog.user_id == int(user_id))

    total = query.count()
    limit = 50
    offset = max(0, (page - 1) * limit)
    logs = query.order_by(WorkflowAuditLog.created_at.desc()).offset(offset).limit(limit).all()

    action_labels = {
        "claim": "Nhận biên tập",
        "save_text": "Lưu bản sửa",
        "approve": "Duyệt xuất bản",
        "reject": "Từ chối / Loại bỏ",
        "archive": "Lưu trữ",
        "auto_video": "Tạo video tự động",
    }

    status_labels = {
        "new": "Tin mới",
        "claimed": "Đã nhận",
        "editing": "Đang sửa",
        "approved": "Đã duyệt",
        "completed": "Hoàn tất",
    }

    users = db.query(User).filter(User.is_active == True).all()

    f = {
        "action": action,
        "user_id": user_id,
    }

    return templates.TemplateResponse(
        "audit.html",
        {
            "request": request,
            "current_user": user,
            "logs": logs,
            "total": total,
            "page": page,
            "f": f,
            "action_labels": action_labels,
            "status_labels": status_labels,
            "users": users,
        }
    )
