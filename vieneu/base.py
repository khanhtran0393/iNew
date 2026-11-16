from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class BaseTTS(ABC):
    @abstractmethod
    def infer_batch(self, texts: List[str], **kwargs) -> List[bytes]:
        pass

    def apply_watermark(self, audio_bytes: bytes) -> bytes:
        return audio_bytes
