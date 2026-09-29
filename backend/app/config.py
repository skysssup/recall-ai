from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RECALL_",
        env_file=".env",
        extra="ignore",
    )

    database_url: str = f"sqlite:///{Path(__file__).resolve().parent.parent / 'recall.db'}"
    api_token: str = "dev-token-change-me"
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "chrome-extension://*",
    ]
    host: str = "127.0.0.1"
    port: int = 8787
    # Cards with this many lapses are flagged as leeches.
    leech_threshold: int = 8


settings = Settings()
