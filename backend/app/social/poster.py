from __future__ import annotations

import traceback
from pathlib import Path

from .. import jobs
from ..config import settings
from ..models import ClipMeta


def _caption_parts(clip: ClipMeta, override_caption: str | None, override_tags: list[str] | None):
    caption = override_caption if override_caption is not None else clip.caption
    tags = override_tags if override_tags is not None else clip.hashtags
    return caption, tags


def post_to_platforms(job_id: str, clip_id: str, platforms: list[str],
                      caption_override: str | None = None,
                      hashtags_override: list[str] | None = None) -> dict:
    job = jobs.get(job_id)
    if not job:
        raise RuntimeError("job not found")
    clip = next((c for c in job.clips if c.id == clip_id), None)
    if not clip:
        raise RuntimeError("clip not found")

    caption, tags = _caption_parts(clip, caption_override, hashtags_override)
    results: dict[str, str] = dict(clip.posted)

    for platform in platforms:
        try:
            if platform == "youtube":
                from . import youtube
                vid = youtube.upload_short(
                    file_path=clip.file_path,
                    title=clip.title,
                    description=caption,
                    tags=tags,
                )
                results["youtube"] = f"ok:{vid}"
            elif platform == "tiktok":
                from . import tiktok
                pub_id = tiktok.upload_video(
                    file_path=clip.file_path,
                    title=caption or clip.title,
                    hashtags=tags,
                )
                results["tiktok"] = f"ok:{pub_id}"
            elif platform == "instagram":
                from . import instagram
                # IG needs a public URL to the file.
                rel = Path(clip.file_path).resolve().relative_to(settings.data_path)
                public_url = f"{settings.public_base_url.rstrip('/')}/files/{rel.as_posix()}"
                ig_id = instagram.publish_reel(public_url, caption, tags)
                results["instagram"] = f"ok:{ig_id}"
            else:
                results[platform] = "error:unknown platform"
        except Exception as e:
            traceback.print_exc()
            results[platform] = f"error:{type(e).__name__}:{e}"

    jobs.update_clip(job_id, clip_id, posted=results)
    return results
