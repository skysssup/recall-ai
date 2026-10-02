from pathlib import Path
from typing import Annotated, Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


_DEFAULT_CORS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]


def _clean_origins(v: Any) -> list[str]:
    if v is None:
        return list(_DEFAULT_CORS)
    if isinstance(v, str):
        parts = [p.strip() for p in v.split(",") if p.strip()]
        cleaned = [p for p in parts if "*" not in p]
        return cleaned or list(_DEFAULT_CORS)
    if isinstance(v, list):
        cleaned = [str(o).strip() for o in v if str(o).strip() and "*" not in str(o)]
        return cleaned or list(_DEFAULT_CORS)
    return list(_DEFAULT_CORS)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RECALL_",
        env_file=".env",
        extra="ignore",
    )

    database_url: str = f"sqlite:///{Path(__file__).resolve().parent.parent / 'recall.db'}"
    api_token: str = ""
    # NoDecode: accept comma-separated env strings without JSON parsing.
    cors_origins: Annotated[list[str], NoDecode] = list(_DEFAULT_CORS)
    host: str = "127.0.0.1"
    port: int = 8787
    leech_threshold: int = 8
    relax_loopback_check: bool = False

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v: Any) -> list[str]:
        return _clean_origins(v)


settings = Settings()
