"""STT server-side — faster-whisper tiny CPU int8.

Lazy singleton: model dimuat saat request pertama (~75MB, ~40s download
sekali, lalu ~2s load dari cache). infer ~0.5s untuk 3s audio 16kHz.
Tanpa dependensi audio (av pecah di py3.14): decode PCM pakai stdlib wave.

Endpoint /api/stt terima raw PCM16 mono 16kHz (body bytes) atau WAV,
kembalikan {text, language, confidence}.
ponytail: streaming chunked (VAD-gated 320ms) saat WebSocket audio ada.
"""
import io
import threading
import time
import wave

_MODEL = None
_MODEL_LOCK = threading.Lock()
_LOAD_S = 0.0


def _get_model():
    global _MODEL, _LOAD_S
    if _MODEL is not None:
        return _MODEL
    with _MODEL_LOCK:
        if _MODEL is not None:
            return _MODEL
        from faster_whisper import WhisperModel
        t0 = time.time()
        _MODEL = WhisperModel("tiny", device="cpu", compute_type="int8")
        _LOAD_S = time.time() - t0
        return _MODEL


def _to_float32(data: bytes):
    """WAV atau raw PCM16 mono 16kHz -> numpy float32. Stdlib only."""
    import numpy as np
    raw = data
    if data[:4] == b"RIFF":
        with wave.open(io.BytesIO(data), "rb") as w:
            if w.getnchannels() != 1 or w.getsampwidth() != 2:
                raise ValueError("need mono 16-bit wav")
            raw = w.readframes(w.getnframes())
    return np.frombuffer(raw, dtype=np.int16).astype("float32") / 32768.0


def transcribe(data: bytes, language: str = "id") -> dict:
    """Transkripsi bytes audio. Max ~30s (480k samples) per request."""
    import numpy as np  # noqa: F401 — pastikan numpy ada sebelum model
    audio = _to_float32(data)
    if len(audio) > 480000:
        audio = audio[:480000]
    if len(audio) < 8000:
        return {"text": "", "language": language, "confidence": 0.0}
    m = _get_model()
    t0 = time.time()
    segs, info = m.transcribe(audio, beam_size=1, language=language,
                              vad_filter=True,
                              vad_parameters={"min_silence_duration_ms": 500})
    parts, probs = [], []
    for s in segs:
        parts.append(s.text)
        if getattr(s, "avg_logprob", None) is not None:
            import math
            probs.append(math.exp(s.avg_logprob))
    return {
        "text": " ".join(parts).strip(),
        "language": info.language,
        "confidence": round(sum(probs) / len(probs), 3) if probs else 0.0,
        "infer_s": round(time.time() - t0, 2),
        "model_load_s": round(_LOAD_S, 1),
    }


def available() -> bool:
    try:
        import faster_whisper  # noqa: F401
        return True
    except ImportError:
        return False
