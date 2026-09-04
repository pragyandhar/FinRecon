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

    # Guardrails against a JOIN on a non-unique field (e.g. "status" or
    # "currency" instead of an actual ID) producing a combinatorial
    # explosion of rows — which then cascades into thousands of
    # "exceptions" and burns the AI budget investigating them one by one.
    max_join_output_rows: int = 20_000
    max_join_output_multiplier: int = 10  # merged rows vs max(len(left), len(right))

    # Hard ceiling on how many EXCEPTION records one job will ever send
    # to the AI investigator, no matter how many exist. Protects the
    # per-job AI spend even if something upstream still produces an
    # unexpectedly large exception count.
    max_exceptions_to_investigate: int = 200

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
