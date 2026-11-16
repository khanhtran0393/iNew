"""First-time setup wizard routes."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from app.web.templating import templates

router = APIRouter(prefix="/setup", tags=["setup"])


@router.get("", response_class=HTMLResponse)
async def setup_page(request: Request):
    return templates.TemplateResponse("setup.html", {"request": request})
