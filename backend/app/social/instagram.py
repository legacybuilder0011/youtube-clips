from __future__ import annotations

"""Instagram Reels upload via Graph API.

Reference: https://developers.facebook.com/docs/instagram-api/guides/content-publishing

Two-step publish: create an IG container pointing at a publicly fetchable
video URL, poll until FINISHED, then publish. Requires:
- IG Business account connected to a Facebook page
- A long-lived page access token with instagram_content_publish
- Clip reachable via ``settings.public_base_url`` (expose your server publicly,
  e.g. with ngrok or a real domain).
"""

import time

import httpx

from ..config import settings

GRAPH = "https://graph.facebook.com/v19.0"


def _check() -> None:
    if not settings.ig_user_id or not settings.ig_access_token:
        raise RuntimeError("IG_USER_ID and IG_ACCESS_TOKEN must be set")


def publish_reel(public_video_url: str, caption: str, hashtags: list[str]) -> str:
    _check()
    full_caption = caption
    if hashtags:
        full_caption = (caption + "\n\n" + " ".join(f"#{h}" for h in hashtags)).strip()
    full_caption = full_caption[:2200]

    with httpx.Client(timeout=120) as client:
        # 1. Create container
        r = client.post(
            f"{GRAPH}/{settings.ig_user_id}/media",
            params={
                "media_type": "REELS",
                "video_url": public_video_url,
                "caption": full_caption,
                "share_to_feed": "true",
                "access_token": settings.ig_access_token,
            },
        )
        r.raise_for_status()
        creation_id = r.json()["id"]

        # 2. Poll status
        for _ in range(60):  # up to ~5 minutes
            s = client.get(
                f"{GRAPH}/{creation_id}",
                params={"fields": "status_code,status", "access_token": settings.ig_access_token},
            )
            s.raise_for_status()
            status = s.json().get("status_code")
            if status == "FINISHED":
                break
            if status == "ERROR":
                raise RuntimeError(f"IG container processing error: {s.json()}")
            time.sleep(5)
        else:
            raise RuntimeError("IG container did not finish in time")

        # 3. Publish
        p = client.post(
            f"{GRAPH}/{settings.ig_user_id}/media_publish",
            params={"creation_id": creation_id, "access_token": settings.ig_access_token},
        )
        p.raise_for_status()
        return p.json()["id"]
