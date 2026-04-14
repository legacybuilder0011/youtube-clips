from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import settings
from .models import ClipMeta, Job, JobStatus

_lock = threading.Lock()


def _job_file(job_id: str) -> Path:
    return settings.jobs_path / f"{job_id}.json"


def create_job(url: str) -> Job:
    job = Job(id=uuid.uuid4().hex[:12], url=url)
    save(job)
    return job


def save(job: Job) -> None:
    job.updated_at = datetime.utcnow()
    with _lock:
        _job_file(job.id).write_text(job.model_dump_json(indent=2))


def get(job_id: str) -> Optional[Job]:
    p = _job_file(job_id)
    if not p.exists():
        return None
    return Job.model_validate_json(p.read_text())


def list_jobs() -> list[Job]:
    out: list[Job] = []
    for f in sorted(settings.jobs_path.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            out.append(Job.model_validate_json(f.read_text()))
        except Exception:
            continue
    return out


def update_status(job_id: str, status: JobStatus, progress: int = 0, message: str = "") -> None:
    job = get(job_id)
    if not job:
        return
    job.status = status
    if progress:
        job.progress = progress
    if message:
        job.message = message
    save(job)


def add_clip(job_id: str, clip: ClipMeta) -> None:
    job = get(job_id)
    if not job:
        return
    job.clips.append(clip)
    save(job)


def update_clip(job_id: str, clip_id: str, **changes) -> Optional[ClipMeta]:
    job = get(job_id)
    if not job:
        return None
    for idx, c in enumerate(job.clips):
        if c.id == clip_id:
            data = c.model_dump()
            data.update(changes)
            job.clips[idx] = ClipMeta(**data)
            save(job)
            return job.clips[idx]
    return None


def mark_failed(job_id: str, err: str) -> None:
    job = get(job_id)
    if not job:
        return
    job.status = "failed"
    job.error = err
    save(job)
