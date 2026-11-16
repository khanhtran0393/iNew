import logging
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db, SessionLocal
from app.models import User, RawPost, AiUsageLog
from app.services import studio_store, ai_image
from app.services.studio_store import StudioError
from app.web.auth import require_editor

logger = logging.getLogger("ak_news.studio")

router = APIRouter(prefix="/api/studio", tags=["studio"])

SUGGEST_SYSTEM = (
    "Bạn là biên tập viên hình ảnh của tòa soạn. Viết MỘT đoạn mô tả ngắn (2-4 câu, tiếng Việt) "
    "để AI vẽ ảnh minh hoạ cho bản tin: bối cảnh, chủ thể, góc máy, ánh sáng, phong cách ảnh báo chí. "
    "Ảnh minh hoạ chung, không vẽ người thật cụ thể, không chữ, không logo, không cảnh máu me. "
    "Chỉ trả về đoạn mô tả."
)


class AiImageRequest(BaseModel):
    post_id: int
    prompt: str
    aspect: str = "9:16"


class SuggestRequest(BaseModel):
    post_id: Optional[int] = None
    text: Optional[str] = None


class TemplateRequest(BaseModel):
    name: str
    design: Dict[str, Any]


class ProjectRequest(BaseModel):
    post_id: int
    project: Dict[str, Any]


def _error(msg: str, status_code: int = 400) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"success": False, "error": msg})


@router.get("/assets")
def list_studio_assets(post_id: Optional[int] = None, current_user: User = Depends(require_editor)):
    assets = studio_store.list_assets(post_id)
    return {"success": True, "assets": assets}


@router.post("/assets")
async def upload_asset(
    post_id: Optional[int] = Form(None),
    file: UploadFile = File(...),
    current_user: User = Depends(require_editor)
):
    try:
        content = await file.read()
        asset = studio_store.save_image(post_id, content)
        return {"success": True, "asset": asset}
    except StudioError as e:
        return _error(str(e))
    except Exception as e:
        logger.error(f"Upload error: {e}")
        return _error("Lỗi khi tải ảnh lên.")


@router.post("/ai-image")
async def generate_ai_image(
    req: AiImageRequest,
    current_user: User = Depends(require_editor),
    db: Session = Depends(get_db)
):
    post = db.query(RawPost).filter_by(id=req.post_id).first()
    if not post:
        return _error("Không tìm thấy bài viết.")

    try:
        data = await ai_image.generate(req.prompt, req.aspect, topic_id=post.topic_id)
        asset = studio_store.save_image(req.post_id, data)
        return {"success": True, "asset": asset}
    except Exception as e:
        logger.error(f"AI image gen error: {e}")
        return _error(str(e))


@router.post("/ai-image/suggest")
async def suggest_image_prompt(
    req: SuggestRequest,
    current_user: User = Depends(require_editor),
    db: Session = Depends(get_db)
):
    source_text = req.text or ""
    if req.post_id:
        post = db.query(RawPost).filter_by(id=req.post_id).first()
        if post:
            source_text = post.cleaned_text or post.title or source_text

    if not source_text:
        return _error("Vui lòng cung cấp post_id hoặc nội dung text.")

    try:
        from app.services.ai_copilot import generate_title_summary
        summary = await generate_title_summary(source_text)
        prompt = f"{summary.get('title', '')}. {summary.get('summary', '')}".strip()
        return {"success": True, "prompt": prompt or source_text[:200]}
    except Exception:
        return {"success": True, "prompt": source_text[:200]}


@router.get("/templates")
def get_templates(current_user: User = Depends(require_editor)):
    return {"success": True, "templates": studio_store.list_templates()}


@router.get("/templates/{template_id}")
def get_single_template(template_id: str, current_user: User = Depends(require_editor)):
    try:
        t = studio_store.get_template(template_id)
        return {"success": True, "template": t}
    except Exception as e:
        return _error(str(e), 404)


@router.post("/templates")
def create_template(req: TemplateRequest, current_user: User = Depends(require_editor)):
    try:
        tid = studio_store.save_template(None, req.dict(), current_user.full_name or current_user.username)
        return {"success": True, "template_id": tid}
    except Exception as e:
        return _error(str(e))


@router.delete("/templates/{template_id}")
def delete_single_template(template_id: str, current_user: User = Depends(require_editor)):
    studio_store.delete_template(template_id)
    return {"success": True}


@router.post("/project")
def save_studio_project(req: ProjectRequest, current_user: User = Depends(require_editor)):
    try:
        pid = studio_store.save_project(req.project, current_user.username, req.post_id)
        return {"success": True, "project_id": pid}
    except Exception as e:
        return _error(str(e))
