from typing import List
from .base import BaseTTS

class V3NanoVieNeuTTS(BaseTTS):
    def infer_batch(self, texts: List[str], **kwargs) -> List[bytes]:
        return [b"" for _ in texts]
