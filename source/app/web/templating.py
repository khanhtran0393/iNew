"""Jinja2 Templates engine configuration."""

from pathlib import Path
from fastapi.templating import Jinja2Templates
from app.config import settings

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

# Register globals
templates.env.globals["app_version"] = settings.APP_VERSION
templates.env.globals["key_bot"] = settings.KEY_BOT_USERNAME
templates.env.globals["update_info"] = None
templates.env.globals["video_languages"] = ["vi", "en"]
templates.env.globals["default_video_language"] = "vi"


def make_templates() -> Jinja2Templates:
    return templates
