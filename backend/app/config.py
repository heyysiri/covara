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
    # Claude (Anthropic) is the primary provider. Key from https://platform.claude.com
    anthropic_api_key: str = ""
    anthropic_model: str = ""  # defaults to claude-opus-5-5
    # No API key? Covara can use your logged-in Claude Code session through its headless mode
    # (`claude -p`). Path is auto-detected (PATH, then the VS Code extension's bundled binary).
    claude_use_cli: bool = True
    claude_cli_path: str = ""
    claude_cli_model: str = ""  # optional --model override for the CLI (default: your session's model)
    gemini_api_key: str = ""
    gemini_model: str = ""
    groq_api_key: str = ""
    groq_model: str = ""
    sarvam_api_key: str = ""

    # Pipeline
    cache_dir: Path = BACKEND_DIR / ".cache"
    llm_timeout_s: int = 180
    # Demo mode: replay cached LLM results only, never call providers (W1 safety net).
    demo_mode: bool = False

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.frontend_origin.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
