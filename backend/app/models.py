from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

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
    thumbnail_path: Optional[str] = None
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
    clips_count: Optional[int] = None
    min_seconds: Optional[int] = None
    max_seconds: Optional[int] = None
    aspect: Optional[str] = None


class PostRequest(BaseModel):
    platforms: list[Literal["youtube", "tiktok", "instagram"]]
    caption_override: Optional[str] = None
    hashtags_override: Optional[list[str]] = None


class ViralMoment(BaseModel):
    start: float
    end: float
    title: str
    caption: str
    hashtags: list[str] = Field(default_factory=list)
    reason: str = ""
    virality_score: int = 0
