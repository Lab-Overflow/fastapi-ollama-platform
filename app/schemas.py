from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    model: str | None = None
    temperature: float = 0.7
    session_id: str | None = None


class ChatResponse(BaseModel):
    content: str
    model: str
    usage: dict[str, int] = Field(default_factory=dict)


class SessionCreateResponse(BaseModel):
    session_id: str


class SessionHistoryResponse(BaseModel):
    session_id: str
    messages: list[ChatMessage]


class IngestDoc(BaseModel):
    id: str | None = None
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class IngestRequest(BaseModel):
    documents: list[IngestDoc]


class IngestResponse(BaseModel):
    ingested: int
    total_chunks: int


class RagQueryRequest(BaseModel):
    query: str
    top_k: int = 4
    model: str | None = None


class RagCitation(BaseModel):
    id: str
    score: float
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class RagQueryResponse(BaseModel):
    answer: str
    citations: list[RagCitation]
    model: str


class ExtractRequest(BaseModel):
    text: str
    schema: dict[str, Any] = Field(
        description="JSON Schema describing the fields to extract",
    )
    model: str | None = None


class ExtractResponse(BaseModel):
    data: dict[str, Any]
    model: str
