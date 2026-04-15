from __future__ import annotations

import tempfile
from collections.abc import Callable
from pathlib import Path

from yt_dlp import YoutubeDL

from ..config import settings


def _resolve_cookies_file() -> str | None:
    """Return a path to a Netscape cookies.txt file, or None.

    Supports two env-var flavors:
      - YT_DLP_COOKIES_FILE: an absolute path already on disk
      - YT_DLP_COOKIES: raw file contents pasted into the env var; we write it
        to a tempfile and return that path.
    """
    path = (settings.yt_dlp_cookies_file or "").strip()
    if path and Path(path).is_file():
        return path

    raw = settings.yt_dlp_cookies or ""
    if raw.strip():
        tmp = tempfile.NamedTemporaryFile(
            prefix="ytdlp-cookies-", suffix=".txt", delete=False, mode="w", encoding="utf-8"
        )
        tmp.write(raw)
        tmp.flush()
        tmp.close()
        return tmp.name

    return None


def download_video(
    url: str, out_dir: Path, progress: Callable[[int, str], None] | None = None
) -> dict:
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

    ydl_opts: dict = {
        # Keep the selector forgiving: "best" guarantees a result when the
        # stricter selectors filter every format out (which happens on old
        # yt-dlp versions that can't decrypt YouTube's newer signature cipher).
        "format": (
            "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/"
            "bv*[height<=1080]+ba/"
            "b[height<=1080]/"
            "bv*+ba/b/best"
        ),
        "merge_output_format": "mp4",
        "outtmpl": str(out_dir / "%(id)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [hook],
        "noplaylist": True,
        "http_headers": {"User-Agent": settings.yt_dlp_user_agent},
        "retries": 3,
    }

    cookies_path = _resolve_cookies_file()
    if cookies_path:
        ydl_opts["cookiefile"] = cookies_path
    else:
        # No cookies available: fall back to the android player client,
        # which is less aggressive about the "confirm you're not a bot" gate
        # at the cost of a narrower format list.
        ydl_opts["extractor_args"] = {"youtube": {"player_client": ["android", "web"]}}

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
