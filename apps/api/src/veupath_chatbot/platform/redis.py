"""Redis connection management for event sourcing."""

from collections.abc import Awaitable

from redis.asyncio import Redis

from veupath_chatbot.platform.config import get_settings
from veupath_chatbot.platform.logging import get_logger

logger = get_logger(__name__)

_state: dict[str, Redis | None] = {"redis": None}


async def init_redis() -> Redis:
    """Initialize the Redis connection pool."""
    settings = get_settings()
    redis = Redis.from_url(
        settings.redis_url,
        decode_responses=False,
    )
    result = redis.ping()
    if isinstance(result, Awaitable):
        await result
    logger.info("Redis connected", url=settings.redis_url)
    _state["redis"] = redis
    return redis


def get_redis() -> Redis:
    """Get the Redis client. Must call init_redis() first."""
    redis = _state["redis"]
    if redis is None:
        msg = "Redis not initialized. Call init_redis() during startup."
        raise RuntimeError(msg)
    return redis


async def close_redis() -> None:
    """Close the Redis connection pool."""
    redis = _state["redis"]
    if redis:
        await redis.aclose()
        _state["redis"] = None
        logger.info("Redis connection closed")
