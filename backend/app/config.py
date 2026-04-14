from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM
    llm_provider: Literal["anthropic", "openai"] = "anthropic"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-6"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    # Whisper
    whisper_model: str = "base"
    whisper_compute_type: str = "int8"
    whisper_device: str = "cpu"

    # Clips
    clip_min_seconds: int = 15
    clip_max_seconds: int = 60
    clips_per_video: int = 5
    clip_aspect: str = "9:16"
    caption_font: str = "Arial"
    caption_font_size: int = 52
    caption_color: str = "&H00FFFFFF"
    caption_outline_color: str = "&H00000000"
    caption_words_per_line: int = 4

    # Storage
    data_dir: str = "./data"

    # YouTube
    youtube_client_secrets_file: str = "./secrets/youtube_client_secret.json"
    youtube_token_file: str = "./secrets/youtube_token.json"

    # TikTok
    tiktok_access_token: str = ""
    tiktok_open_id: str = ""

    # Instagram
    ig_user_id: str = ""
    ig_access_token: str = ""
    public_base_url: str = "http://localhost:8000"

    @property
    def data_path(self) -> Path:
        p = Path(self.data_dir).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def downloads_path(self) -> Path:
        p = self.data_path / "downloads"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def clips_path(self) -> Path:
        p = self.data_path / "clips"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def jobs_path(self) -> Path:
        p = self.data_path / "jobs"
        p.mkdir(parents=True, exist_ok=True)
        return p


settings = Settings()
