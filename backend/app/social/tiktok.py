from __future__ import annotations

"""TikTok Content Posting API — direct upload flow.

Reference: https://developers.tiktok.com/doc/content-posting-api-reference-direct-post

Requires an approved TikTok developer app with ``video.upload`` and
``video.publish`` scopes, plus an access token for the user. Not to be used
with the Content Posting API sandbox if you want real public posts.
"""

import math
import os
from pathlib import Path

import httpx

from ..config import settings

API = "https://open.tiktokapis.com/v2"
CHUNK_SIZE = 10 * 1024 * 1024  # 10MB


def _auth_headers() -> dict:
    if not settings.tiktok_access_token:
        raise RuntimeError("TIKTOK_ACCESS_TOKEN is not set")
    return {"Authorization": f"Bearer {settings.tiktok_access_token}"}


def upload_video(file_path: str, title: str, hashtags: list[str]) -> str:
    """Upload a video and publish directly. Returns the publish_id."""
    path = Path(file_path)
    file_size = path.stat().st_size
    chunk_size = min(CHUNK_SIZE, file_size)
    total_chunks = max(1, math.ceil(file_size / chunk_size))

    tagged_title = title
    if hashtags:
        tagged_title = (title + " " + " ".join(f"#{h}" for h in hashtags)).strip()
    tagged_title = tagged_title[:2200]

    # 1. Initialize upload
    init_body = {
        "post_info": {
            "title": tagged_title,
            "privacy_level": "PUBLIC_TO_EVERYONE",
            "disable_duet": False,
            "disable_comment": False,
            "disable_stitch": False,
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": file_size,
            "chunk_size": chunk_size,
            "total_chunk_count": total_chunks,
        },
    }
    with httpx.Client(timeout=120) as client:
        r = client.post(
            f"{API}/post/publish/video/init/",
            headers={**_auth_headers(), "Content-Type": "application/json; charset=UTF-8"},
            json=init_body,
        )
        r.raise_for_status()
        data = r.json()["data"]
        publish_id = data["publish_id"]
        upload_url = data["upload_url"]

        # 2. Upload chunks via PUT
        with path.open("rb") as fh:
            for i in range(total_chunks):
                start = i * chunk_size
                end = min(file_size - 1, (i + 1) * chunk_size - 1)
                fh.seek(start)
                chunk = fh.read(end - start + 1)
                headers = {
                    "Content-Range": f"bytes {start}-{end}/{file_size}",
                    "Content-Length": str(len(chunk)),
                    "Content-Type": "video/mp4",
                }
                put = client.put(upload_url, content=chunk, headers=headers)
                put.raise_for_status()

    return publish_id


def fetch_status(publish_id: str) -> dict:
    with httpx.Client(timeout=60) as client:
        r = client.post(
            f"{API}/post/publish/status/fetch/",
            headers={**_auth_headers(), "Content-Type": "application/json; charset=UTF-8"},
            json={"publish_id": publish_id},
        )
        r.raise_for_status()
        return r.json()
