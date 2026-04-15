from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

JobStatus = Literal[
    "queued",
    "downloading",
    "transcribing",
    "analyzing",
    "clipping",
    "done",
    "failed",
]


class ClipMeta(BaseModel):
    id: str
    job_id: str
    start: float
    end: float
    title: str
    caption: str
    hashtags: list[str] = Field(default_factory=list)
    reason: str = ""
    virality_score: int = 0
    file_path: str
    thumbnail_path: str | None = None
    posted: dict[str, str] = Field(default_factory=dict)  # platform -> status/id


class Job(BaseModel):
    id: str
    url: str
    status: JobStatus = "queued"
    message: str = ""
    progress: int = 0  # 0..100
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    video_title: str = ""
    video_duration: float = 0.0
    source_file: str = ""
    transcript_file: str = ""
    clips: list[ClipMeta] = Field(default_factory=list)
    error: str = ""


class CreateJobRequest(BaseModel):
    url: str
    clips_count: int | None = None
    min_seconds: int | None = None
    max_seconds: int | None = None
    aspect: str | None = None


class PostRequest(BaseModel):
    platforms: list[Literal["youtube", "tiktok", "instagram"]]
    caption_override: str | None = None
    hashtags_override: list[str] | None = None


class ViralMoment(BaseModel):
    start: float
    end: float
    title: str
    caption: str
    hashtags: list[str] = Field(default_factory=list)
    reason: str = ""
    virality_score: int = 0
