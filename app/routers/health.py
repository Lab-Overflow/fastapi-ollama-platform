import logging

from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.deps import get_ollama
from app.ollama_client import OllamaService

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/models")
async def models(
    ollama: OllamaService = Depends(get_ollama),
    settings: Settings = Depends(get_settings),
) -> dict[str, list[str]]:
    try:
        models = await ollama.list_models()
        if models:
            return {"models": models}
    except Exception as exc:
        logging.exception("Failed to list Ollama models: %s", exc)

    # Degraded fallback: keep UI usable and allow server-side default model flow.
    return {"models": [settings.chat_model]}
