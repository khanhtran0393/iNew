import os
import re
import json
import logging
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from app.config import settings
from app.database import SessionLocal
from app.models import RawPost, MediaItem, MediaType, AiUsageLog
from app.services.tasks import spawn

logger = logging.getLogger("ak_news.ai_media")

MEDIA_AI_ACTIONS = {
    "image_describe": {
        "title": "🖼️ Mô tả & đọc chữ",
        "media_type": MediaType.PHOTO,
        "system": (
