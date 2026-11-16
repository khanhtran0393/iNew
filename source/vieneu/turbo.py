"""Turbo ONNX Runtime TTS Engine."""

import numpy as np
from .base import BaseVieNeuTTS


class TurboVieNeuTTS(BaseVieNeuTTS):
    def synthesize(self, text: str, voice_key: str = "", speed: float = 1.0, **kwargs) -> np.ndarray:
        return np.zeros(24000, dtype=np.float32)


class TurboGPUVieNeuTTS(TurboVieNeuTTS):
    pass
