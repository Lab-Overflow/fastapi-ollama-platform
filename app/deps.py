from fastapi import Request

from app.ollama_client import OllamaService
from app.rag.pipeline import RagPipeline
from app.session import SessionStore


def get_ollama(request: Request) -> OllamaService:
    return request.app.state.ollama


def get_sessions(request: Request) -> SessionStore:
    return request.app.state.sessions


def get_rag(request: Request) -> RagPipeline:
    return request.app.state.rag
