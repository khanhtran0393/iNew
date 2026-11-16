"""V3 Nano Lightweight Neural TTS Model Implementation."""

import numpy as np
from typing import Optional
from .base import BaseVieNeuTTS


class V3NanoVieNeuTTS(BaseVieNeuTTS):
    def __init__(self, assets_dir: Optional[str] = None, **kwargs):
        super().__init__(assets_dir=assets_dir, **kwargs)

    def synthesize(self, text: str, voice_key: str = "", speed: float = 1.0, **kwargs) -> np.ndarray:
        sr = 24000
        duration = max(0.5, len(text) * 0.05 / max(speed, 0.1))
        return np.zeros(int(duration * sr), dtype=np.float32)
