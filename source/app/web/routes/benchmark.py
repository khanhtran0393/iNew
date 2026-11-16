"""Benchmark and system health page."""

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse

from app.models import User
from app.web.auth import require_admin
from app.web.templating import templates
from app.benchmark_report import build_report

router = APIRouter(prefix="/benchmark", tags=["benchmark"])


@router.get("", response_class=HTMLResponse)
async def benchmark_page(request: Request, user: User = Depends(require_admin)):
    report = build_report(24)
    return templates.TemplateResponse("benchmark.html", {"request": request, "user": user, "report": report})
