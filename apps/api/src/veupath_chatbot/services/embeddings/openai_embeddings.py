from __future__ import annotations

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass

from veupath_chatbot.platform.config import get_settings


def _chunks(items: list[str], *, size: int) -> Iterable[list[str]]:
    if size <= 0:
        raise ValueError("chunk size must be > 0")
    for i in range(0, len(items), size):
        yield items[i : i + size]


@dataclass(frozen=True)
class OpenAIEmbeddings:
    """Small wrapper around OpenAI embeddings with batching."""

    model: str
    batch_size: int = 128

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        settings = get_settings()
        try:
            # `kani[openai]` pulls in the official OpenAI client.
            from openai import AsyncOpenAI
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                "OpenAI SDK not available. Install `openai` (or `kani[openai]`)."
            ) from exc

        client = AsyncOpenAI(api_key=settings.openai_api_key or None)
        vectors: list[list[float]] = []
        # Keep ordering stable.
        for batch in _chunks(texts, size=self.batch_size):
            # The SDK accepts list[str] input.
            resp = await client.embeddings.create(model=self.model, input=batch)
            # resp.data is in the same order as input.
            vectors.extend([d.embedding for d in resp.data])
            # Be polite to upstream if we're doing large ingests.
            await asyncio.sleep(0)

        if len(vectors) != len(texts):  # pragma: no cover (SDK contract)
            raise RuntimeError("Embedding count mismatch")
        return vectors


async def embed_one(*, text: str, model: str) -> list[float]:
    """Convenience helper for one-off vector size detection."""
    embedder = OpenAIEmbeddings(model=model, batch_size=1)
    return (await embedder.embed_texts([text]))[0]
