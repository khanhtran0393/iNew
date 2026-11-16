from typing import List
def infer_batch(texts: List[str], **kwargs) -> List[bytes]:
    return [b"" for _ in texts]
