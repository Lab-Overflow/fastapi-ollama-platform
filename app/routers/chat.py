from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from app.config import Settings, get_settings
from app.deps import get_ollama, get_sessions
from app.ollama_client import OllamaService
from app.schemas import ChatRequest, ChatResponse
from app.session import SessionStore

router = APIRouter(prefix="/chat", tags=["chat"])


def _resolve_messages(req: ChatRequest, sessions: SessionStore) -> list[dict[str, str]]:
    history = sessions.get(req.session_id) if req.session_id else []
    return history + [m.model_dump() for m in req.messages]


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
        async for token in ollama.chat_stream(
            messages=messages, model=model, temperature=req.temperature
        ):
            full.append(token)
            yield {"event": "token", "data": token}
        assistant_msg = "".join(full)
        if req.session_id:
            sessions.append(
                req.session_id,
                [m.model_dump() for m in req.messages]
                + [{"role": "assistant", "content": assistant_msg}],
            )
        yield {"event": "done", "data": ""}

    return EventSourceResponse(event_gen())
