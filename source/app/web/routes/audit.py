"""Audit trail and workflow logs inspection."""

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, WorkflowAuditLog
from app.web.auth import require_admin
from app.web.templating import templates

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_class=HTMLResponse)
async def audit_page(request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    logs = db.query(WorkflowAuditLog).order_by(WorkflowAuditLog.id.desc()).limit(100).all()
    return templates.TemplateResponse("audit.html", {"request": request, "user": user, "logs": logs})
