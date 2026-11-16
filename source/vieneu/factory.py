"""VieNeu TTS Factory Router."""

from typing import Any
from .v3turbo import V3TurboVieNeuTTS
from .v3nano import V3NanoVieNeuTTS
from .turbo import TurboVieNeuTTS
from .standard import VieNeuTTS
from .fast import FastVieNeuTTS
from .remote import RemoteVieNeuTTS
from .core_xpu import XPUVieNeuTTS


def Vieneu(mode: str = "v3turbo", **kwargs) -> Any:
    mode_lower = (mode or "v3turbo").lower()
    if mode_lower in ("v3turbo", "turbo_v3"):
        return V3TurboVieNeuTTS(**kwargs)
    elif mode_lower in ("v3nano", "nano_v3"):
        return V3NanoVieNeuTTS(**kwargs)
    elif mode_lower in ("remote", "api"):
        return RemoteVieNeuTTS(**kwargs)
    elif mode_lower in ("fast", "gpu"):
        return FastVieNeuTTS(**kwargs)
    elif mode_lower == "turbo":
        return TurboVieNeuTTS(**kwargs)
    elif mode_lower == "xpu":
        return XPUVieNeuTTS(**kwargs)
    else:
        return VieNeuTTS(**kwargs)
