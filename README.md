# Viral Clip Generator

Paste a YouTube URL. The app downloads the video, transcribes it with Whisper,
asks an LLM (Claude or GPT) to pick the funniest / most viral moments, cuts
each into a vertical short with burned-in word-level captions, and lets you
auto-post to YouTube Shorts, TikTok, and Instagram Reels.

## Pipeline

1. **Download** — `yt-dlp` pulls the MP4 (<=1080p).
2. **Transcribe** — `faster-whisper` produces word-level timestamps.
3. **Analyze** — Claude / GPT returns N ranked viral moments with title,
   caption, hashtags, virality_score, and tight start/end boundaries.
4. **Clip** — `ffmpeg` cuts each moment, reframes to 9:16 with a blurred
   background cover, and burns in karaoke-style captions via an ASS file.
5. **Post** — Optional one-click publish to YouTube / TikTok / Instagram.

## Requirements

- Python 3.10+
- `ffmpeg` on PATH
- An LLM API key: `ANTHROPIC_API_KEY` *or* `OPENAI_API_KEY`
- For social posting (all optional):
  - YouTube: OAuth Desktop client JSON from Google Cloud Console
  - TikTok: approved developer app with Content Posting API + user access token
  - Instagram: IG Business account + long-lived page token
    (clips must be fetchable from a public URL, so you'll need ngrok or a real
    domain for `PUBLIC_BASE_URL`)

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env       # fill in API keys
```

For YouTube, drop your downloaded OAuth JSON at
`secrets/youtube_client_secret.json`. The first upload will open a browser for
consent and cache the token at `secrets/youtube_token.json`.

## Run

```bash
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

Open http://localhost:8000 and paste a YouTube URL.

## API

- `POST /api/jobs` — `{ url, clips_count?, min_seconds?, max_seconds?, aspect? }`
- `GET /api/jobs` — list
- `GET /api/jobs/{id}` — detail (poll for progress/clips)
- `GET /api/clips/{job_id}/{clip_id}/video` — download the mp4
- `GET /api/clips/{job_id}/{clip_id}/thumb` — jpg poster
- `POST /api/clips/{job_id}/{clip_id}/post` —
  `{ platforms: ["youtube"|"tiktok"|"instagram"], caption_override?, hashtags_override? }`

## Notes & limitations

- **Transcription is CPU-bound**. On a laptop, a 30-minute video with the
  `base` model takes several minutes. Use `WHISPER_MODEL=small` or `tiny` for
  speed, or set `WHISPER_DEVICE=cuda` + `WHISPER_COMPUTE_TYPE=float16` if you
  have a GPU.
- **The job runs in a FastAPI `BackgroundTask`**, so only one worker at a
  time. For production, swap in Celery/RQ. Single-user local use is fine.
- **TikTok direct-post** requires an *approved* developer app. During sandbox
  you'll be restricted to a test user. The `unaudited_client` sandbox flow
  uses a different endpoint — adjust `tiktok.py` if needed.
- **Instagram** needs your server reachable publicly. During dev:
  `ngrok http 8000` then set `PUBLIC_BASE_URL=https://<id>.ngrok.io`.
- **Legal**: you are responsible for respecting YouTube's ToS and the
  copyrights of source videos. Only clip videos you have rights to use.
