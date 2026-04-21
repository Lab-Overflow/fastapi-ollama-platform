from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ollama_host: str = "http://127.0.0.1:11434"
    chat_model: str = "qwen3:8b"
    embed_model: str = "nomic-embed-text"
    extract_model: str = "qwen3:8b"
    max_concurrency: int = 4
    request_timeout: int = 120
    log_level: str = "INFO"
    session_max_turns: int = 20
    session_ttl_seconds: int = 3600
    session_storage_dir: str = "data/sessions"


@lru_cache
def get_settings() -> Settings:
    return Settings()
