from typing import Optional
from .v3turbo import V3TurboVieNeuTTS
from .v3nano import V3NanoVieNeuTTS

class Vieneu:
    @staticmethod
    def load(model_type: str = "v3turbo", **kwargs):
        if model_type == "v3turbo":
            return V3TurboVieNeuTTS(**kwargs)
        elif model_type == "v3nano":
            return V3NanoVieNeuTTS(**kwargs)
        raise ValueError(f"Unknown model_type: {model_type}")
