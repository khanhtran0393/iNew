"""Base TTS interface and common presets."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Dict, Any
import numpy as np


class BaseVieNeuTTS(ABC):
    def __init__(self, assets_dir: Optional[str] = None, **kwargs):
        self.assets_dir = Path(assets_dir) if assets_dir else Path(__file__).resolve().parent / "assets"
        self._preset_voices = {}

    @abstractmethod
    def synthesize(self, text: str, voice_key: str = "", speed: float = 1.0, **kwargs) -> np.ndarray:
        pass

    def save_wav(self, wav: np.ndarray, path: str, sr: int = 24000):
        import soundfile as sf
        sf.write(path, wav, sr)
