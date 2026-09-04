from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Central configuration. Every AI call site reads `openai_model` from
    here — there is exactly one place to change which model FinRecon uses."""

    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    database_url: str = "sqlite:///./backend/storage/finrecon.db"
    raw_storage_dir: str = "./backend/storage/raw"

    max_file_size_mb: int = 25
    max_plan_retries: int = 2
    default_amount_tolerance: float = 1.0
    enable_llm_fallback: bool = True
    enable_chat: bool = True

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    @property
    def raw_storage_path(self) -> Path:
        path = REPO_ROOT / self.raw_storage_dir.lstrip("./")
        path.mkdir(parents=True, exist_ok=True)
        return path


settings = Settings()
