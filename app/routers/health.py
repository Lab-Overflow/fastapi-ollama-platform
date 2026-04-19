from fastapi import APIRouter, Depends

from app.deps import get_ollama
from app.ollama_client import OllamaService

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/models")
async def models(ollama: OllamaService = Depends(get_ollama)) -> dict[str, list[str]]:
    return {"models": await ollama.list_models()}
