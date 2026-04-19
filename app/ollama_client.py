import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from ollama import AsyncClient

from app.config import Settings


class OllamaService:
    """Thin async wrapper around Ollama with a concurrency guard."""

    def __init__(self, settings: Settings) -> None:
        self._client = AsyncClient(host=settings.ollama_host, timeout=settings.request_timeout)
        self._sem = asyncio.Semaphore(settings.max_concurrency)
        self._settings = settings

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.7,
        fmt: str | dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        async with self._sem:
            return await self._client.chat(
                model=model,
                messages=messages,
                options={"temperature": temperature},
                format=fmt,
                stream=False,
            )

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        async with self._sem:
            stream = await self._client.chat(
                model=model,
                messages=messages,
                options={"temperature": temperature},
                stream=True,
            )
            async for chunk in stream:
                token = chunk.get("message", {}).get("content", "")
                if token:
                    yield token

    async def embed(self, texts: list[str], model: str) -> list[list[float]]:
        async with self._sem:
            resp = await self._client.embed(model=model, input=texts)
            return list(resp["embeddings"])

    async def extract_json(
        self,
        prompt: str,
        schema: dict[str, Any],
        model: str,
    ) -> dict[str, Any]:
        """Use Ollama structured outputs (format=schema) for reliable JSON."""
        resp = await self.chat(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You extract structured data. Respond with JSON only, "
                        "matching the provided schema exactly."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            model=model,
            temperature=0.0,
            fmt=schema,
        )
        content = resp.get("message", {}).get("content", "{}")
        return json.loads(content)

    async def list_models(self) -> list[str]:
        resp = await self._client.list()
        return [m.get("model", m.get("name", "")) for m in resp.get("models", [])]
