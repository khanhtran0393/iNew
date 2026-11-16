"""Core audio mathematics, framing and crossfading utilities."""

import math
import numpy as np

CODEC_SAMPLES_PER_FRAME = 320
ENCODER_PAD_CODE = -1
MAX_FRAMES_PER_PHONE = 4
SINGLE_WORD_MAX_FRAMES = 50


def pad_to_codec_frame(wav: np.ndarray, sr: int = 24000) -> np.ndarray:
    n_samp = len(wav)
    rem = n_samp % CODEC_SAMPLES_PER_FRAME
    if rem != 0:
        pad = CODEC_SAMPLES_PER_FRAME - rem
        wav = np.concatenate([wav, np.zeros(pad, dtype=np.float32)])
    return wav


def strip_encoder_pad_frame(codes: np.ndarray) -> np.ndarray:
    if codes.ndim > 0 and codes.shape[-1] > 0 and codes[..., -1] == ENCODER_PAD_CODE:
        return codes[..., :-1]
    return codes


def is_cue_only(phonemes: str) -> bool:
    clean = phonemes.replace("<|emotion_", "").replace("|>", "").strip()
    return not any(c.isalpha() for c in clean)


def max_expected_frames(phonemes: str) -> int:
    stripped = phonemes.replace("<|emotion_", "").replace("|>", "")
    eff_len = len(stripped.split())
    if eff_len <= 1:
        return SINGLE_WORD_MAX_FRAMES
    return int(math.ceil(eff_len * MAX_FRAMES_PER_PHONE) + 20)


def trim_and_fade(wav: np.ndarray, sr: int = 24000, thresh_db: float = -45.0, fade_s: float = 0.01) -> np.ndarray:
    if len(wav) == 0:
        return wav
    fade_len = int(fade_s * sr)
    if fade_len > 0 and len(wav) > fade_len * 2:
        ramp = 0.5 * (1.0 - np.cos(np.linspace(0, np.pi, fade_len)))
        wav = wav.copy()
        wav[:fade_len] *= ramp
        wav[-fade_len:] *= ramp[::-1]
    return wav


def join_audio_chunks(chunks: list, sr: int = 24000, silence_p: float = 0.1) -> np.ndarray:
    if not chunks:
        return np.zeros(0, dtype=np.float32)
    silence = np.zeros(int(silence_p * sr), dtype=np.float32)
    out = []
    for i, c in enumerate(chunks):
        out.append(c)
        if i < len(chunks) - 1:
            out.append(silence)
    return np.concatenate(out)
