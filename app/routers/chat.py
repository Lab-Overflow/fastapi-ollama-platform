import logging
import uuid

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from app.config import Settings, get_settings
from app.deps import get_ollama, get_sessions
from app.ollama_client import OllamaService
from app.schemas import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    SessionCreateResponse,
    SessionHistoryResponse,
)
from app.session import SessionStore

router = APIRouter(prefix="/chat", tags=["chat"])


def _resolve_messages(req: ChatRequest, sessions: SessionStore) -> list[dict[str, str]]:
    history = sessions.get(req.session_id) if req.session_id else []
    return history + [m.model_dump() for m in req.messages]


@router.post("/sessions", response_model=SessionCreateResponse)
async def create_session() -> SessionCreateResponse:
    return SessionCreateResponse(session_id=uuid.uuid4().hex)


@router.get("/sessions/{session_id}", response_model=SessionHistoryResponse)
async def get_session(
    session_id: str,
    sessions: SessionStore = Depends(get_sessions),
) -> SessionHistoryResponse:
    history = [ChatMessage(**m) for m in sessions.get(session_id)]
    return SessionHistoryResponse(session_id=session_id, messages=history)


@router.post("", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    ollama: OllamaService = Depends(get_ollama),
    sessions: SessionStore = Depends(get_sessions),
    settings: Settings = Depends(get_settings),
) -> ChatResponse:
    model = req.model or settings.chat_model
    messages = _resolve_messages(req, sessions)
    resp = await ollama.chat(messages=messages, model=model, temperature=req.temperature)
    content = resp.get("message", {}).get("content", "")

    if req.session_id:
        sessions.append(
            req.session_id,
            [m.model_dump() for m in req.messages] + [{"role": "assistant", "content": content}],
        )

    usage = {
        "prompt_eval_count": resp.get("prompt_eval_count", 0),
        "eval_count": resp.get("eval_count", 0),
    }
    return ChatResponse(content=content, model=model, usage=usage)


@router.post("/stream")
async def chat_stream(
    req: ChatRequest,
    ollama: OllamaService = Depends(get_ollama),
    sessions: SessionStore = Depends(get_sessions),
    settings: Settings = Depends(get_settings),
) -> EventSourceResponse:
    model = req.model or settings.chat_model
    messages = _resolve_messages(req, sessions)

    async def event_gen():
        full = []
        try:
            async for token in ollama.chat_stream(
                messages=messages, model=model, temperature=req.temperature
            ):
                full.append(token)
                yield {"event": "token", "data": token}
        except Exception as exc:
            logging.exception("stream chat failed")
            yield {"event": "error", "data": str(exc) or "stream failed"}
            yield {"event": "done", "data": ""}
            return

        assistant_msg = "".join(full)
        if req.session_id:
            sessions.append(
                req.session_id,
                [m.model_dump() for m in req.messages]
                + [{"role": "assistant", "content": assistant_msg}],
            )
        yield {"event": "done", "data": ""}

    return EventSourceResponse(event_gen())
