from __future__ import annotations

import subprocess
from pathlib import Path

from ..config import settings


def _seconds_to_ass_time(t: float) -> str:
    if t < 0:
        t = 0
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t - h * 3600 - m * 60
    return f"{h:d}:{m:02d}:{s:05.2f}"


def _ass_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")


def build_word_captions_ass(
    words: list[dict],
    clip_start: float,
    clip_end: float,
    out_path: Path,
    resolution: tuple[int, int],
) -> Path:
    """Build an ASS subtitle file that highlights words as they are spoken.

    Each chunk of N words (CAPTION_WORDS_PER_LINE) appears at the time its first
    word starts, and disappears when its last word ends. Within each chunk, the
    currently-spoken word is highlighted yellow.
    """
    w_per_line = settings.caption_words_per_line
    font = settings.caption_font
    size = settings.caption_font_size
    primary = settings.caption_color
    outline = settings.caption_outline_color
    width, height = resolution

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{size},{primary},&H000000FF,{outline},&H64000000,-1,0,0,0,100,100,0,0,1,4,2,2,60,60,{int(height*0.18)},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    # Keep only words overlapping this clip window, shift times to clip-local
    local_words = []
    for w in words:
        ws = float(w["start"]) - clip_start
        we = float(w["end"]) - clip_start
        if we <= 0 or ws >= (clip_end - clip_start):
            continue
        local_words.append({
            "start": max(0.0, ws),
            "end": min(clip_end - clip_start, we),
            "word": w["word"].strip(),
        })

    events = []
    # group into chunks of N words
    for i in range(0, len(local_words), w_per_line):
        chunk = local_words[i:i + w_per_line]
        if not chunk:
            continue
        chunk_start = chunk[0]["start"]
        chunk_end = chunk[-1]["end"]
        # Render one event per highlighted-word state within the chunk.
        for j, active in enumerate(chunk):
            seg_start = active["start"]
            seg_end = active["end"] if j < len(chunk) - 1 else chunk_end
            pieces = []
            for k, w in enumerate(chunk):
                word = _ass_escape(w["word"])
                if k == j:
                    pieces.append(r"{\c&H0000FFFF&\b1}" + word + r"{\r}")
                else:
                    pieces.append(word)
            text = " ".join(pieces)
            events.append(
                f"Dialogue: 0,{_seconds_to_ass_time(seg_start)},{_seconds_to_ass_time(seg_end)},Default,,0,0,0,,{text}"
            )
        # Final gap from last word end to chunk_end isn't needed here because we already extended last segment.

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")
    return out_path


def _aspect_to_dims(aspect: str, base_height: int = 1920) -> tuple[int, int]:
    if aspect == "9:16":
        return 1080, 1920
    if aspect == "16:9":
        return 1920, 1080
    if aspect == "1:1":
        return 1080, 1080
    return 1080, 1920


def cut_and_caption(
    source_video: str,
    start: float,
    end: float,
    words: list[dict],
    out_path: Path,
    aspect: str | None = None,
) -> Path:
    """Cut [start,end] from source, reframe to target aspect with a blurred
    background cover, and burn in word-level captions."""
    aspect = aspect or settings.clip_aspect
    W, H = _aspect_to_dims(aspect)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    ass_path = out_path.with_suffix(".ass")
    build_word_captions_ass(words, start, end, ass_path, (W, H))

    duration = max(0.1, end - start)

    # Build filter:
    # [0]split into two streams; one scaled to fill (cropped blurred bg), one
    # scaled to fit (centered). Then overlay, then burn subtitles.
    # Escape the subtitle path: backslashes -> forward slashes, `:` -> `\:`
    # (ffmpeg filter option separator).
    escaped_ass = str(ass_path).replace("\\", "/").replace(":", r"\:")
    vf = (
        f"[0:v]split=2[bg][fg];"
        f"[bg]scale={W}:{H}:force_original_aspect_ratio=increase,"
        f"crop={W}:{H},boxblur=20:1,setsar=1[bg2];"
        f"[fg]scale={W}:{H}:force_original_aspect_ratio=decrease,setsar=1[fg2];"
        f"[bg2][fg2]overlay=(W-w)/2:(H-h)/2,"
        f"ass='{escaped_ass}'"
    )

    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{start:.3f}",
        "-i", source_video,
        "-t", f"{duration:.3f}",
        "-filter_complex", vf,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "160k",
        "-movflags", "+faststart",
        str(out_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {proc.stderr[-2000:]}")
    return out_path


def make_thumbnail(clip_path: Path, out_path: Path, at: float = 1.0) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-ss", f"{at:.2f}", "-i", str(clip_path),
        "-frames:v", "1", "-q:v", "3", str(out_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg thumbnail failed: {proc.stderr[-1000:]}")
    return out_path
