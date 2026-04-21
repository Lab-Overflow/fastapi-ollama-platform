import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.ollama_client import OllamaService
from app.rag.pipeline import RagPipeline
from app.rag.store import InMemoryVectorStore
from app.routers import chat, extract, health, rag, ui
from app.session import SessionStore


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)

    ollama = OllamaService(settings)
    store = InMemoryVectorStore()
    app.state.ollama = ollama
    app.state.sessions = SessionStore(
        max_turns=settings.session_max_turns,
        ttl_seconds=settings.session_ttl_seconds,
        storage_dir=settings.session_storage_dir,
    )
    app.state.rag = RagPipeline(ollama=ollama, store=store, embed_model=settings.embed_model)
    yield


app = FastAPI(
    title="FastAPI + Ollama Platform",
    version="1.0.0",
    description=(
        "Production-grade local LLM backend: streaming chat, retrieval-augmented "
        "generation and schema-constrained structured extraction, served behind "
        "an async concurrency-controlled Ollama client."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(rag.router)
app.include_router(extract.router)
app.include_router(ui.router)

static_dir = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")
