from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ollama_host: str = "http://localhost:11434"
    chat_model: str = "qwen3:8b"
    embed_model: str = "nomic-embed-text"
    extract_model: str = "qwen3:8b"
    max_concurrency: int = 4
    request_timeout: int = 120
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
