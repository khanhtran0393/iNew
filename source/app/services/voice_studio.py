"""Vietnamese Neural TTS Voice Synthesis Studio."""

import os
from pathlib import Path
from typing import Dict, Any, List
from app.config import settings

_VOICES = [
    {"key": "vi-VN-HoaiMyNeural", "name": "Hoài My (Nữ miền Bắc)", "gender": "female"},
    {"key": "vi-VN-NamMinhNeural", "name": "Nam Minh (Nam miền Bắc)", "gender": "male"},
    {"key": "Bình (nam miền Bắc)", "name": "Bình (Nam Bắc - AI Neural)", "gender": "male"},
    {"key": "Ly (nữ miền Bắc)", "name": "Ly (Nữ Bắc - AI Neural)", "gender": "female"},
    {"key": "Ngọc (nữ miền Bắc)", "name": "Ngọc (Nữ Bắc - AI Neural)", "gender": "female"},
    {"key": "Tuyên (nam miền Bắc)", "name": "Tuyên (Nam Bắc - AI Neural)", "gender": "male"},
    {"key": "Vinh (nam miền Nam)", "name": "Vinh (Nam Nam - AI Neural)", "gender": "male"},
    {"key": "Đoan (nữ miền Nam)", "name": "Đoan (Nữ Nam - AI Neural)", "gender": "female"},
]


def list_available_voices() -> List[Dict[str, Any]]:
    return _VOICES


def recover_stale_jobs():
    pass


def start_engine_loading():
    pass


async def synthesize_voice(text: str, voice_key: str, speed: float = 1.0) -> Path:
    out_file = settings.voices_dir / f"tts_{os.getpid()}_{int(speed*100)}.wav"
    out_file.touch()
    return out_file
