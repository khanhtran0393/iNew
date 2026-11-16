from pathlib import Path
from typing import Any, Mapping, Optional, Dict, List
from fastapi import Request
from starlette.templating import Jinja2Templates as _Jinja2Templates
from starlette.background import BackgroundTask

from app.config import settings
from app.resources import get_asset_path
from app.services.updates import get_cached_update_info
from app.services.video_languages import choices as get_video_languages, default_voice_for


class CompatibleJinja2Templates(_Jinja2Templates):
    def TemplateResponse(
        self,
        *args,
        **kwargs
    ):
        # Support both (request, name, context) and (name, context)
        if len(args) >= 2 and isinstance(args[0], str) and isinstance(args[1], dict):
            name = args[0]
            context = args[1]
            request = context.get("request") or kwargs.get("request")
            remaining_args = args[2:]
            return super().TemplateResponse(request, name, context, *remaining_args, **kwargs)
        elif "name" in kwargs and "context" in kwargs and isinstance(kwargs["context"], dict) and "request" not in kwargs:
            req = kwargs["context"].get("request")
            return super().TemplateResponse(request=req, **kwargs)
        return super().TemplateResponse(*args, **kwargs)


templates_dir = get_asset_path("app/web/templates")
templates = CompatibleJinja2Templates(directory=str(templates_dir))

# Helper wrappers for Jinja2 environment globals
def _update_info() -> Dict[str, Any]:
    return get_cached_update_info()

def _video_languages() -> List[Dict[str, Any]]:
    return get_video_languages()

def _default_video_language(lang: str = "vi") -> str:
    return default_voice_for(lang)

# Register environment globals matching the original binary
templates.env.globals["APP_VERSION"] = settings.VERSION
templates.env.globals["app_version"] = settings.VERSION
templates.env.globals["KEY_BOT_USERNAME"] = getattr(settings, "KEY_BOT_USERNAME", "")
templates.env.globals["key_bot"] = getattr(settings, "KEY_BOT_USERNAME", "")
templates.env.globals["update_info"] = _update_info
templates.env.globals["video_languages"] = _video_languages
templates.env.globals["default_video_language"] = _default_video_language
