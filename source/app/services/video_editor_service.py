"""Video Editor project rendering pipeline."""

from pathlib import Path
from app.config import settings


async def render_editor_project(project_data: dict) -> Path:
    out = settings.final_outputs_dir / "project_rendered.mp4"
    out.touch()
    return out
