from pathlib import Path

pkg_dir = Path("sea_g2p")
pkg_dir.mkdir(exist_ok=True)

# 1. sea_g2p/__init__.py
(pkg_dir / "__init__.py").write_text('''"""Southeast Asian Grapheme-to-Phoneme (G2P) library."""
from .g2p import G2P
from .normalizer import Normalizer
from .pipeline import SEAPipeline

__all__ = ["G2P", "Normalizer", "SEAPipeline"]
''', encoding="utf-8")

# 2. sea_g2p/normalizer.py
(pkg_dir / "normalizer.py").write_text('''import os
from typing import List, Optional

try:
    import sea_g2p_rs
    NormalizerRS = getattr(sea_g2p_rs, "Normalizer", None)
except ImportError:
    NormalizerRS = None

SUPPORTED_LANGS = ["vi", "id", "th"]


class Normalizer:
    def __init__(self, lang: str = "vi", db_path: Optional[str] = None):
        if lang not in SUPPORTED_LANGS:
            raise ValueError(f"lang must be one of {SUPPORTED_LANGS}, got {lang}")
        self.lang = lang
        self.db_path = db_path
        if NormalizerRS:
            self._rs_normalizer = NormalizerRS(lang, db_path) if db_path else NormalizerRS(lang)
        else:
            self._rs_normalizer = None

    def normalize(self, text: str, punc_norm: bool = True) -> str:
        if not text:
            return ""
        if self._rs_normalizer and hasattr(self._rs_normalizer, "normalize"):
            return self._rs_normalizer.normalize(text, punc_norm)
        return text.strip()

    def normalize_batch(self, texts: List[str], punc_norm: bool = True) -> List[str]:
        return [self.normalize(t, punc_norm) for t in texts]

    def audit(self, text: str) -> dict:
        return {"text": text, "lang": self.lang}
''', encoding="utf-8")

# 3. sea_g2p/g2p.py
(pkg_dir / "g2p.py").write_text('''import os
import logging
from typing import List, Optional

logger = logging.getLogger("sea_g2p")

try:
    import sea_g2p_rs
    _RustG2P = getattr(sea_g2p_rs, "G2P", None)
except ImportError:
    _RustG2P = None

SUPPORTED_LANGS = ["vi", "id", "th"]


class G2P:
    def __init__(self, lang: str = "vi", db_path: Optional[str] = None, **kwargs):
        if lang not in SUPPORTED_LANGS:
            raise ValueError(f"lang must be one of {SUPPORTED_LANGS}, got {lang}")
        self.lang = lang
        self.db_path = db_path
        if _RustG2P:
            self._rust_engine = _RustG2P(lang, db_path) if db_path else _RustG2P(lang)
            logger.debug(f"Initialized Rust G2P engine with {lang}")
        else:
            self._rust_engine = None

    def convert(self, text: str, punc_norm: bool = True) -> str:
        if not text:
            return ""
        if self._rust_engine and hasattr(self._rust_engine, "convert"):
            return self._rust_engine.convert(text, punc_norm)
        return text.strip()

    def phonemize(self, text: str, punc_norm: bool = True) -> str:
        return self.convert(text, punc_norm)

    def phonemize_batch(self, texts: List[str], punc_norm: bool = True) -> List[str]:
        return [self.convert(t, punc_norm) for t in texts]
''', encoding="utf-8")

# 4. sea_g2p/pipeline.py
(pkg_dir / "pipeline.py").write_text('''from typing import Dict, Any, List
from .normalizer import Normalizer
from .g2p import G2P


class SEAPipeline:
    def __init__(self, lang: str = "vi"):
        self.lang = lang
        self.normalizer = Normalizer(lang=lang)
        self.g2p = G2P(lang=lang)

    def run(self, text: str, punc_norm: bool = True) -> Dict[str, Any]:
        normalized = self.normalizer.normalize(text, punc_norm=punc_norm)
        phonemes = self.g2p.convert(normalized, punc_norm=punc_norm)
        return {
            "normalized_text": normalized,
            "phonemes": phonemes
        }
''', encoding="utf-8")

print("Generated sea_g2p package (4 files)")
