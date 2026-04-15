from __future__ import annotations

import json
from pathlib import Path

from ..config import settings

_model = None


def _get_model():
    global _model
    if _model is None:
        # Lazy import so the app can start without the model loaded
        from faster_whisper import WhisperModel

        _model = WhisperModel(
            settings.whisper_model,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
        )
    return _model


def transcribe(video_path: str, out_path: Path) -> dict:
    """Transcribe with word-level timestamps. Writes JSON to out_path.

    Returns dict {segments: [...], words: [...]}.
    """
    model = _get_model()
    segments_iter, info = model.transcribe(
        video_path,
        word_timestamps=True,
        vad_filter=True,
    )
    segments = []
    words = []
    for seg in segments_iter:
        s = {
            "start": float(seg.start),
            "end": float(seg.end),
            "text": seg.text.strip(),
            "words": [],
        }
        if seg.words:
            for w in seg.words:
                wd = {
                    "start": float(w.start) if w.start is not None else s["start"],
                    "end": float(w.end) if w.end is not None else s["end"],
                    "word": w.word,
                }
                s["words"].append(wd)
                words.append(wd)
        segments.append(s)

    result = {
        "language": info.language,
        "duration": info.duration,
        "segments": segments,
        "words": words,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2))
    return result
