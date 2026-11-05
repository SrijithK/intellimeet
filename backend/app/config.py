from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DATABASE_URL = "postgresql+psycopg://intellimeet:intellimeet@localhost:5433/intellimeet"


class Settings(BaseSettings):
    app_name: str = "IntelliMeet"
    debug: bool = False
    database_url: str = DEFAULT_DATABASE_URL

    llm_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    ollama_num_ctx: int = 8192
    extraction_enabled: bool = True

    # Transcripts in this folder are ingested on startup (idempotent). Unset = no seeding.
    seed_dir: Optional[str] = None

    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
