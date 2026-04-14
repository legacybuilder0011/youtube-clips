from __future__ import annotations

from pathlib import Path
from typing import Callable

from yt_dlp import YoutubeDL


def download_video(url: str, out_dir: Path, progress: Callable[[int, str], None] | None = None) -> dict:
    """Download a YouTube video, return {file, title, duration}."""
    out_dir.mkdir(parents=True, exist_ok=True)

    def hook(d):
        if progress is None:
            return
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            dl = d.get("downloaded_bytes") or 0
            pct = int(dl * 100 / total) if total else 0
            progress(pct, f"downloading {pct}%")
        elif d.get("status") == "finished":
            progress(100, "download complete")

    ydl_opts = {
        "format": "bv*[height<=1080]+ba/b[height<=1080]",
        "merge_output_format": "mp4",
        "outtmpl": str(out_dir / "%(id)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [hook],
        "noplaylist": True,
    }

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

    # Resolve final filename (after merge). yt-dlp gives us the right extension via info after merge.
    video_id = info.get("id")
    title = info.get("title", "untitled")
    duration = float(info.get("duration") or 0.0)

    # Find the merged file
    candidates = list(out_dir.glob(f"{video_id}.*"))
    # Prefer mp4 if present.
    mp4s = [c for c in candidates if c.suffix.lower() == ".mp4"]
    file_path = (mp4s or candidates)[0] if candidates else None
    if not file_path:
        raise RuntimeError("downloaded file not found")

    return {
        "file": str(file_path),
        "title": title,
        "duration": duration,
        "id": video_id,
    }
