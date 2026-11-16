"""Audio normalization and formatting helpers."""

import numpy as np


def normalize_audio(wav: np.ndarray, target_db: float = -20.0) -> np.ndarray:
    rms = np.sqrt(np.mean(wav**2))
    if rms > 0:
        scalar = 10 ** (target_db / 20) / rms
        return wav * scalar
    return wav
