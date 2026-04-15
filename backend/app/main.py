from __future__ import annotations

import os
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from . import jobs
from .config import settings
from .models import CreateJobRequest, Job, PostRequest
from .pipeline.orchestrator import run_job
from .social.poster import post_to_platforms

app = FastAPI(title="YouTube Viral Clip Generator")

# CORS — allow the Lovable (or other) frontend to call this API. Set
# ALLOWED_ORIGINS in the environment to a comma-separated list, e.g.
# "https://my-app.lovable.app,http://localhost:5173". Defaults to "*" for dev.
_origins_raw = os.environ.get("ALLOWED_ORIGINS", "*")
_origins = [o.strip() for o in _origins_raw.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- Static files for the SPA and for clip downloads ----
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Serve the data dir so clips/thumbs are reachable (used by the UI and by IG).
app.mount("/files", StaticFiles(directory=str(settings.data_path)), name="files")


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    html_file = STATIC_DIR / "index.html"
    return HTMLResponse(html_file.read_text(encoding="utf-8"))


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "llm_provider": settings.llm_provider,
        "whisper_model": settings.whisper_model,
    }


@app.get("/api/debug/ytdlp")
def debug_ytdlp() -> dict:
    """Report whether YouTube cookies + yt-dlp are wired up correctly."""
    import yt_dlp

    from .pipeline.downloader import _resolve_cookies_file

    cookies_path = _resolve_cookies_file()
    cookies_info: dict = {"found": cookies_path is not None}
    if cookies_path:
        try:
            size = Path(cookies_path).stat().st_size
            cookies_info["size_bytes"] = size
            with open(cookies_path, encoding="utf-8", errors="replace") as f:
                first_line = f.readline().strip()
            cookies_info["header"] = first_line
        except Exception as e:
            cookies_info["error"] = str(e)
    return {
        "yt_dlp_version": getattr(yt_dlp.version, "__version__", "unknown"),
        "cookies": cookies_info,
        "env_has_YT_DLP_COOKIES": bool(os.environ.get("YT_DLP_COOKIES")),
        "env_has_YT_DLP_COOKIES_FILE": bool(os.environ.get("YT_DLP_COOKIES_FILE")),
    }


@app.post("/api/jobs", response_model=Job)
def create_job(req: CreateJobRequest, bg: BackgroundTasks) -> Job:
    if not req.url.strip():
        raise HTTPException(400, "url required")
    job = jobs.create_job(req.url.strip())
    bg.add_task(
        run_job,
        job.id,
        clips_count=req.clips_count,
        aspect=req.aspect,
        min_s=req.min_seconds,
        max_s=req.max_seconds,
    )
    return job


@app.get("/api/jobs", response_model=list[Job])
def list_jobs() -> list[Job]:
    return jobs.list_jobs()


@app.get("/api/jobs/{job_id}", response_model=Job)
def get_job(job_id: str) -> Job:
    j = jobs.get(job_id)
    if not j:
        raise HTTPException(404, "not found")
    return j


@app.get("/api/clips/{job_id}/{clip_id}/video")
def clip_video(job_id: str, clip_id: str) -> FileResponse:
    j = jobs.get(job_id)
    if not j:
        raise HTTPException(404, "job not found")
    clip = next((c for c in j.clips if c.id == clip_id), None)
    if not clip:
        raise HTTPException(404, "clip not found")
    return FileResponse(clip.file_path, media_type="video/mp4")


@app.get("/api/clips/{job_id}/{clip_id}/thumb")
def clip_thumb(job_id: str, clip_id: str) -> FileResponse:
    j = jobs.get(job_id)
    if not j:
        raise HTTPException(404, "job not found")
    clip = next((c for c in j.clips if c.id == clip_id), None)
    if not clip or not clip.thumbnail_path:
        raise HTTPException(404, "no thumbnail")
    return FileResponse(clip.thumbnail_path, media_type="image/jpeg")


@app.post("/api/clips/{job_id}/{clip_id}/post")
def post_clip(job_id: str, clip_id: str, req: PostRequest) -> dict:
    return post_to_platforms(
        job_id=job_id,
        clip_id=clip_id,
        platforms=req.platforms,
        caption_override=req.caption_override,
        hashtags_override=req.hashtags_override,
    )
