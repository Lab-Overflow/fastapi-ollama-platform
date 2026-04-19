from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.deps import get_rag
from app.rag.pipeline import RagPipeline
from app.schemas import (
    IngestRequest,
    IngestResponse,
    RagQueryRequest,
    RagQueryResponse,
)

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/ingest", response_model=IngestResponse)
async def ingest(
    req: IngestRequest,
    rag: RagPipeline = Depends(get_rag),
) -> IngestResponse:
    ingested, chunks = await rag.ingest(req.documents)
    return IngestResponse(ingested=ingested, total_chunks=chunks)


@router.post("/query", response_model=RagQueryResponse)
async def query(
    req: RagQueryRequest,
    rag: RagPipeline = Depends(get_rag),
    settings: Settings = Depends(get_settings),
) -> RagQueryResponse:
    model = req.model or settings.chat_model
    answer, citations = await rag.query(req.query, chat_model=model, top_k=req.top_k)
    return RagQueryResponse(answer=answer, citations=citations, model=model)
