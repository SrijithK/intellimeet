from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DATABASE_URL = "postgresql+psycopg://intellimeet:intellimeet@localhost:5433/intellimeet"


class Settings(BaseSettings):
    app_name: str = "IntelliMeet"
    debug: bool = False
    database_url: str = DEFAULT_DATABASE_URL

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
