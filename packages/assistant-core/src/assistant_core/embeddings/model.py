"""The fastembed text-embedding model every embedding caller shares."""

from __future__ import annotations

import os
import threading

from fastembed import TextEmbedding

from assistant_core.platform.logging import get_logger

logger = get_logger(__name__)

MODEL_NAME = "nomic-ai/nomic-embed-text-v1.5"


class _ModelState:
    """Thread-safe singleton holder for the fastembed model."""

    _instance: TextEmbedding | None = None
    _lock: threading.Lock = threading.Lock()

    @classmethod
    def get(cls) -> TextEmbedding:
        """Return the singleton model, loading it on first call."""
        if cls._instance is not None:
            return cls._instance
        with cls._lock:
            if cls._instance is not None:
                return cls._instance
            logger.info("Loading fastembed model", model=MODEL_NAME)
            cache_dir = os.getenv("FASTEMBED_CACHE_DIR") or None
            cls._instance = TextEmbedding(model_name=MODEL_NAME, cache_dir=cache_dir)
            logger.info("Fastembed model loaded")
            return cls._instance


def get_embedding_model() -> TextEmbedding:
    """Return the lazy-loaded fastembed model singleton."""
    return _ModelState.get()


def warm_up_model() -> None:
    """Load the embedding model before the first request."""
    get_embedding_model()
