from typing import List
def infer_torch(texts: List[str], **kwargs) -> List[bytes]:
    return [b"" for _ in texts]
