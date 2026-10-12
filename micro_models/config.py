import json
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

Task = Literal["text", "asr", "tts", "document", "image", "video"]


class Profile(BaseModel):
    task: Task
    model: str = ""
    backend: str = "default"
    system_prompt: str = "Answer accurately and briefly. Say when you do not know."
    language: str = "en"
    voice: str = "af_heart"
    domain_terms: str = ""
    lexicon: dict[str, str] = Field(default_factory=dict)
    fields: dict[str, str] = Field(default_factory=dict)
    adapter_path: str | None = None
    steps: int = Field(default=20, ge=1, le=50)
    guidance_scale: float = Field(default=5.0, ge=0, le=20)


class Settings(BaseModel):
    task: Task = "text"
    data_dir: Path = Path("data")
    profile_path: Path | None = None
    api_key: str = ""
    text_url: str = "http://127.0.0.1:8080/v1"
    text_model: str = "micro-text"
    text_backend: Literal["http", "gguf"] = "http"
    text_api_key: str = ""
    threads: int = Field(default=2, ge=1, le=64)
    max_upload_bytes: int = Field(default=10 * 1024 * 1024, ge=1)
    max_audio_seconds: int = Field(default=60, ge=1, le=600)
    max_document_pages: int = Field(default=8, ge=1, le=100)
    max_image_pixels: int = Field(default=16_000_000, ge=1)
    backend_timeout: int = Field(default=120, ge=1)

    @classmethod
    def from_env(cls):
        values = {name: os.environ[f"MICRO_{name.upper()}"] for name in cls.model_fields
                  if f"MICRO_{name.upper()}" in os.environ}
        return cls(**values)

    @model_validator(mode="after")
    def valid_url(self):
        if not self.text_url.startswith(("http://", "https://")):
            raise ValueError("MICRO_TEXT_URL must be an HTTP(S) server configured by the operator")
        return self

    def profile(self) -> Profile:
        if self.profile_path:
            profile = Profile(**json.loads(self.profile_path.read_text(encoding="utf-8")))
            if profile.task != self.task:
                raise ValueError("Profile task does not match MICRO_TASK")
            return profile
        defaults = {"asr": "tiny.en", "image": "Efficient-Large-Model/Sana_600M_1024px_diffusers",
                    "video": "Lightricks/LTX-Video-0.9.5"}
        return Profile(task=self.task, model=defaults.get(self.task, ""))
