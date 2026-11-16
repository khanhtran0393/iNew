from pathlib import Path
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.web.templating import templates
from app.web.auth import get_current_user, require_admin
from app.services.diagnostics import build_zip
from app.services.maintenance_service import run_maintenance_once

router = APIRouter(tags=["system"])


@router.get("/support")
def support(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse("support.html", {"request": request, "current_user": user})


@router.get("/help")
def help_page(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse("help.html", {"request": request, "current_user": user})


@router.get("/support/diagnostics.zip")
def download_diagnostics_zip(user: User = Depends(require_admin)):
    zip_path = build_zip()
    if not zip_path or not Path(zip_path).exists():
        raise HTTPException(status_code=500, detail="Không thể tạo gói chẩn đoán hệ thống")
    return FileResponse(
        str(zip_path),
        media_type="application/zip",
        filename="inew_diagnostics.zip"
    )


@router.post("/maintenance/run")
def maintenance_run_action(user: User = Depends(require_admin)):
    run_maintenance_once()
    return RedirectResponse(url="/dashboard", status_code=303)

@router.get("/system/settings")
def system_settings(request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    from app.services.desktop import currently_lan, lan_addresses
    from app.config import settings
    return templates.TemplateResponse(
        "system_settings.html",
        {
            "request": request,
            "current_user": user,
            "allow_lan": currently_lan(),
            "lan_ips": lan_addresses(),
            "port": settings.PORT,
            "version": settings.VERSION,
            "app_name": settings.APP_NAME,
        }
    )
