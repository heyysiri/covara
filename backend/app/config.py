"""Application settings, loaded from environment variables / backend/.env."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"

    # Comma-separated list of allowed browser origins (CORS).
    frontend_origin: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Uploads
    max_upload_mb: int = 20
    upload_dir: Path = BACKEND_DIR / "uploads"

    # AI providers. All optional: the app starts without any of them.
    gemini_api_key: str = ""
    gemini_model: str = ""
    groq_api_key: str = ""
    groq_model: str = ""
    sarvam_api_key: str = ""

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.frontend_origin.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
