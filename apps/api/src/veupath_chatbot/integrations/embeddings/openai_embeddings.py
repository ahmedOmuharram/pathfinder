import asyncio
from collections.abc import Iterable
from dataclasses import dataclass, field

from openai import AsyncOpenAI

from veupath_chatbot.platform.config import get_settings
from veupath_chatbot.platform.errors import InternalError


def _chunks(items: list[str], *, size: int) -> Iterable[list[str]]:
    if size <= 0:
        msg = "chunk size must be > 0"
        raise ValueError(msg)
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _resolve_embeddings_config() -> tuple[str, str | None]:
    """Return (api_key, base_url) for the embeddings client.

    Priority:
      1. Explicit ``EMBEDDINGS_BASE_URL`` → use that with the OpenAI key.
      2. ``OPENAI_API_KEY`` set → use OpenAI defaults.
      3. Ollama configured (``OLLAMA_BASE_URL``) → use Ollama as fallback.
    """
    settings = get_settings()

    if settings.embeddings_base_url:
        return settings.openai_api_key or "local", settings.embeddings_base_url

    if settings.openai_api_key:
        return settings.openai_api_key, None

    # Fallback: Ollama for embeddings when no OpenAI key is available.
    return "ollama", settings.ollama_base_url


@dataclass(frozen=True)
class OpenAIEmbeddings:
    """Wrapper around OpenAI-compatible embeddings with batching.

    Works with OpenAI, Ollama, or any server exposing ``/v1/embeddings``.
    """

    model: str
    batch_size: int = 128
    base_url: str | None = field(default=None)

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        api_key, resolved_base = _resolve_embeddings_config()
        effective_base = self.base_url or resolved_base

        async with AsyncOpenAI(api_key=api_key, base_url=effective_base) as client:
            vectors: list[list[float]] = []
            for batch in _chunks(texts, size=self.batch_size):
                resp = await client.embeddings.create(model=self.model, input=batch)
                vectors.extend([d.embedding for d in resp.data])
                await asyncio.sleep(0)

            if len(vectors) != len(texts):  # pragma: no cover (SDK contract)
                raise InternalError(title="Embedding count mismatch")
            return vectors


async def embed_one(*, text: str, model: str) -> list[float]:
    """Convenience helper for one-off vector size detection."""
    embedder = OpenAIEmbeddings(model=model, batch_size=1)
    return (await embedder.embed_texts([text]))[0]
