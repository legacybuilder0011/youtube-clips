from __future__ import annotations

"""YouTube Shorts upload via Data API v3.

Requires an OAuth desktop-app client secret at
``settings.youtube_client_secrets_file``. On first run we launch the browser
consent flow and persist credentials at ``settings.youtube_token_file``.
"""

import os
from pathlib import Path

from ..config import settings

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def _load_credentials():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    token_file = Path(settings.youtube_token_file)
    creds = None
    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            secrets_file = Path(settings.youtube_client_secrets_file)
            if not secrets_file.exists():
                raise RuntimeError(
                    f"Missing YouTube OAuth client secrets at {secrets_file}. "
                    "Create an OAuth Desktop app in Google Cloud Console, "
                    "download the JSON, and place it at that path."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(secrets_file), SCOPES)
            creds = flow.run_local_server(port=0)
        token_file.parent.mkdir(parents=True, exist_ok=True)
        token_file.write_text(creds.to_json())
    return creds


def upload_short(file_path: str, title: str, description: str, tags: list[str]) -> str:
    """Upload an MP4 as a YouTube Short. Returns the video id."""
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    creds = _load_credentials()
    youtube = build("youtube", "v3", credentials=creds)

    # Appending #Shorts to the title/description is the documented hint.
    if "#shorts" not in (title + description).lower():
        description = (description + "\n\n#Shorts").strip()

    body = {
        "snippet": {
            "title": title[:95],
            "description": description[:4900],
            "tags": tags[:30],
            "categoryId": "23",  # Comedy
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(file_path, chunksize=-1, resumable=True, mimetype="video/mp4")
    req = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = req.next_chunk()
    return response["id"]
