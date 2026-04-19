from app.ollama_client import OllamaService
from app.rag.store import InMemoryVectorStore
from app.schemas import IngestDoc, RagCitation


def _chunk_text(text: str, size: int = 800, overlap: int = 120) -> list[str]:
    text = text.strip()
    if len(text) <= size:
        return [text] if text else []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = end - overlap
    return chunks


RAG_PROMPT = """You are a retrieval-augmented assistant. Answer the user strictly using the
context below. If the answer cannot be found, say you don't know.

# Context
{context}

# Question
{question}
"""


class RagPipeline:
    def __init__(self, ollama: OllamaService, store: InMemoryVectorStore, embed_model: str) -> None:
        self._ollama = ollama
        self._store = store
        self._embed_model = embed_model

    async def ingest(self, docs: list[IngestDoc]) -> tuple[int, int]:
        texts: list[str] = []
        metadatas: list[dict] = []
        ids: list[str | None] = []
        for doc in docs:
            for i, chunk in enumerate(_chunk_text(doc.text)):
                texts.append(chunk)
                metadatas.append({**doc.metadata, "source_id": doc.id, "chunk": i})
                ids.append(f"{doc.id}#{i}" if doc.id else None)
        if not texts:
            return 0, 0
        embeddings = await self._ollama.embed(texts, model=self._embed_model)
        self._store.add(texts, embeddings, metadatas, ids)
        return len(docs), len(texts)

    async def query(
        self, question: str, chat_model: str, top_k: int = 4
    ) -> tuple[str, list[RagCitation]]:
        q_emb = (await self._ollama.embed([question], model=self._embed_model))[0]
        hits = self._store.search(q_emb, top_k=top_k)
        if not hits:
            return "Knowledge base is empty. Please ingest documents first.", []

        context = "\n\n".join(f"[{i + 1}] {c.text}" for i, (c, _) in enumerate(hits))
        prompt = RAG_PROMPT.format(context=context, question=question)
        resp = await self._ollama.chat(
            messages=[{"role": "user", "content": prompt}],
            model=chat_model,
            temperature=0.2,
        )
        answer = resp.get("message", {}).get("content", "")
        citations = [
            RagCitation(id=c.id, score=score, text=c.text, metadata=c.metadata)
            for c, score in hits
        ]
        return answer, citations
