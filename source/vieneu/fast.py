"""Fast C++ / ONNX Optimized TTS Engine."""

import numpy as np
from .base import BaseVieNeuTTS


class FastVieNeuTTS(BaseVieNeuTTS):
    def synthesize(self, text: str, voice_key: str = "", speed: float = 1.0, **kwargs) -> np.ndarray:
        return np.zeros(24000, dtype=np.float32)
