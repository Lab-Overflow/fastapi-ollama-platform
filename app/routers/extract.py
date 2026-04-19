from fastapi import APIRouter, Depends, HTTPException

from app.config import Settings, get_settings
from app.deps import get_ollama
from app.ollama_client import OllamaService
from app.schemas import ExtractRequest, ExtractResponse

router = APIRouter(prefix="/extract", tags=["extract"])


@router.post("", response_model=ExtractResponse)
async def extract(
    req: ExtractRequest,
    ollama: OllamaService = Depends(get_ollama),
    settings: Settings = Depends(get_settings),
) -> ExtractResponse:
    model = req.model or settings.extract_model
    try:
        data = await ollama.extract_json(prompt=req.text, schema=req.schema, model=model)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Structured extraction failed: {exc}") from exc
    return ExtractResponse(data=data, model=model)
