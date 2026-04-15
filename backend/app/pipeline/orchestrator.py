from __future__ import annotations

import traceback
import uuid
from pathlib import Path

from .. import jobs
from ..config import settings
from ..models import ClipMeta
from .analyzer import find_viral_moments
from .clipper import cut_and_caption, make_thumbnail
from .downloader import download_video
from .transcriber import transcribe


def run_job(
    job_id: str,
    clips_count: int | None = None,
    aspect: str | None = None,
    min_s: int | None = None,
    max_s: int | None = None,
) -> None:
    job = jobs.get(job_id)
    if not job:
        return
    clips_count = clips_count or settings.clips_per_video
    aspect = aspect or settings.clip_aspect
    min_s = min_s or settings.clip_min_seconds
    max_s = max_s or settings.clip_max_seconds

    try:
        # ---- 1. Download ----
        jobs.update_status(job_id, "downloading", 5, "starting download")

        def prog(pct, msg):
            jobs.update_status(job_id, "downloading", max(5, min(30, 5 + pct // 4)), msg)

        info = download_video(job.url, settings.downloads_path, progress=prog)
        job = jobs.get(job_id)
        job.source_file = info["file"]
        job.video_title = info["title"]
        job.video_duration = info["duration"]
        jobs.save(job)

        # ---- 2. Transcribe ----
        jobs.update_status(job_id, "transcribing", 35, "transcribing audio")
        transcript_path = settings.downloads_path / f"{Path(info['file']).stem}.transcript.json"
        transcript = transcribe(info["file"], transcript_path)
        job = jobs.get(job_id)
        job.transcript_file = str(transcript_path)
        jobs.save(job)

        # ---- 3. Analyze ----
        jobs.update_status(job_id, "analyzing", 55, "finding viral moments")
        moments = find_viral_moments(
            transcript=transcript,
            video_title=info["title"],
            count=clips_count,
            min_seconds=min_s,
            max_seconds=max_s,
        )
        if not moments:
            raise RuntimeError("no viral moments returned by LLM")

        # ---- 4. Clip each ----
        words = transcript.get("words", [])
        clips_dir = settings.clips_path / job_id
        clips_dir.mkdir(parents=True, exist_ok=True)
        total = len(moments)
        for i, m in enumerate(moments, start=1):
            jobs.update_status(
                job_id,
                "clipping",
                60 + int(i * 35 / total),
                f"cutting clip {i}/{total}: {m.title[:40]}",
            )
            clip_id = uuid.uuid4().hex[:8]
            out_file = clips_dir / f"{clip_id}.mp4"
            cut_and_caption(
                source_video=info["file"],
                start=m.start,
                end=m.end,
                words=words,
                out_path=out_file,
                aspect=aspect,
            )
            thumb_file = clips_dir / f"{clip_id}.jpg"
            try:
                make_thumbnail(out_file, thumb_file)
            except Exception:
                thumb_file = None

            clip = ClipMeta(
                id=clip_id,
                job_id=job_id,
                start=m.start,
                end=m.end,
                title=m.title,
                caption=m.caption,
                hashtags=m.hashtags,
                reason=m.reason,
                virality_score=m.virality_score,
                file_path=str(out_file),
                thumbnail_path=str(thumb_file) if thumb_file else None,
            )
            jobs.add_clip(job_id, clip)

        jobs.update_status(job_id, "done", 100, f"{total} clips ready")
    except Exception as e:
        traceback.print_exc()
        jobs.mark_failed(job_id, f"{type(e).__name__}: {e}")
