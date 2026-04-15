from __future__ import annotations

import logging
import os
import tempfile
from collections.abc import Callable
from pathlib import Path

from yt_dlp import YoutubeDL

from ..config import settings

log = logging.getLogger(__name__)


def _resolve_cookies_file() -> str | None:
    """Return a path to a Netscape cookies.txt file, or None.

    Supports two env-var flavors:
      - YT_DLP_COOKIES_FILE: an absolute path already on disk
      - YT_DLP_COOKIES: raw file contents pasted into the env var; we write it
        to a tempfile and return that path.

    Reads both the Pydantic settings value *and* os.environ directly, so the
    env var works even if Pydantic's env-loading is disabled or fails.
    """
    path = (settings.yt_dlp_cookies_file or os.environ.get("YT_DLP_COOKIES_FILE", "")).strip()
    if path and Path(path).is_file():
        log.info("yt-dlp: using cookies file at %s", path)
        return path

    raw = settings.yt_dlp_cookies or os.environ.get("YT_DLP_COOKIES", "")
    if raw and raw.strip():
        # Normalize line endings — some Railway/Render dashboards mangle \r\n.
        raw_norm = raw.replace("\r\n", "\n").replace("\r", "\n")
        if not raw_norm.startswith("# Netscape"):
            raw_norm = "# Netscape HTTP Cookie File\n" + raw_norm
        tmp = tempfile.NamedTemporaryFile(
            prefix="ytdlp-cookies-", suffix=".txt", delete=False, mode="w", encoding="utf-8"
        )
        tmp.write(raw_norm)
        tmp.flush()
        tmp.close()
        log.info("yt-dlp: wrote cookies (%d bytes) from env to %s", len(raw_norm), tmp.name)
        return tmp.name

    log.warning("yt-dlp: no cookies found (YT_DLP_COOKIES / YT_DLP_COOKIES_FILE not set)")
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
        # Use yt-dlp's default selector ("bv*+ba/b") via a sort hint rather
        # than a hard filter. A strict codec/ext filter can match zero formats
        # on certain YouTube responses (especially tv_embedded), leading to
        # "Requested format is not available" even when usable formats exist.
        "format_sort": ["res:1080", "ext:mp4:m4a", "codec:h264", "size"],
        "outtmpl": str(out_dir / "%(id)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [hook],
        "noplaylist": True,
        "http_headers": {"User-Agent": settings.yt_dlp_user_agent},
        "retries": 3,
        # Always try multiple player clients — YouTube returns different
        # format manifests per client and some (web) fail to decrypt on
        # data-center IPs. tv_embedded and ios are the most reliable
        # fallbacks in 2025.
        "extractor_args": {
            "youtube": {
                "player_client": ["tv_embedded", "ios", "web", "android"],
            }
        },
    }

    cookies_path = _resolve_cookies_file()
    if cookies_path:
        ydl_opts["cookiefile"] = cookies_path

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except Exception as e:
        # On format-selection failure, re-probe the URL with process=False so
        # yt-dlp skips format selection and we can see what formats YouTube
        # actually returned. This turns the opaque "Requested format is not
        # available" into an actionable log line.
        if "Requested format is not available" in str(e):
            try:
                probe_opts = {
                    **ydl_opts,
                    "quiet": True,
                    "skip_download": True,
                }
                probe_opts.pop("progress_hooks", None)
                probe_opts.pop("format", None)
                probe_opts.pop("merge_output_format", None)
                with YoutubeDL(probe_opts) as probe:
                    probe_info = probe.extract_info(url, download=False, process=False)
                fmts = probe_info.get("formats", []) if probe_info else []
                if fmts:
                    summary = [
                        f"{f.get('format_id')}:{f.get('ext')}:"
                        f"v={f.get('vcodec')}:a={f.get('acodec')}:"
                        f"h={f.get('height')}"
                        for f in fmts[:30]
                    ]
                    log.error("yt-dlp formats (%d): %s", len(fmts), " | ".join(summary))
                else:
                    # No formats at all — likely an extraction-level issue.
                    keys = list((probe_info or {}).keys())
                    log.error(
                        "yt-dlp probe returned 0 formats. info keys=%s availability=%s",
                        keys,
                        (probe_info or {}).get("availability"),
                    )
            except Exception as probe_err:
                log.error("yt-dlp probe also failed: %s", probe_err)
        raise

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
