"""WDK evaluation with async caching and concurrency control."""

import asyncio
from dataclasses import dataclass

from veupath_chatbot.platform.errors import AppError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONValue
from veupath_chatbot.services.control_tests import (
    IntersectionConfig,
    run_positive_negative_controls,
)
from veupath_chatbot.services.experiment.types import ControlTestResult

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PARALLEL_CONCURRENCY = 4
_CACHE_PRECISION = 5


# ---------------------------------------------------------------------------
# WDK evaluation (cached, semaphore-guarded)
# ---------------------------------------------------------------------------


def _cache_key(params: dict[str, JSONValue]) -> tuple[tuple[str, str], ...]:
    """Build a hashable key from optimised params (rounded floats)."""
    items: list[tuple[str, str]] = []
    for k in sorted(params):
        v = params[k]
        if isinstance(v, float):
            items.append((k, str(round(v, _CACHE_PRECISION))))
        else:
            items.append((k, str(v)))
    return tuple(items)


_CacheKey = tuple[tuple[str, str], ...]
_CacheValue = tuple[ControlTestResult | None, str]
_EvalCache = dict[_CacheKey, _CacheValue]

# Per-key locks prevent duplicate WDK calls when multiple trials in the
# same asyncio.gather batch share identical params.
_KeyLocks = dict[_CacheKey, asyncio.Lock]


@dataclass(frozen=True, slots=True)
class EvalRequest:
    """Bundles the WDK-specific inputs for a single trial evaluation."""

    config: IntersectionConfig
    positive_controls: list[str] | None
    negative_controls: list[str] | None


async def _evaluate_trial(
    request: EvalRequest,
    optimised_params: dict[str, JSONValue],
    sem: asyncio.Semaphore,
    cache: _EvalCache,
    key_locks: _KeyLocks,
) -> tuple[ControlTestResult | None, str]:
    """Run WDK evaluation for a single trial (semaphore-guarded + cached).

    Uses double-checked locking: a fast cache lookup outside the lock,
    then a per-key lock with a second check to prevent duplicate WDK
    calls when ``asyncio.gather`` launches multiple trials with the same
    parameters concurrently.

    Returns (wdk_result_or_None, error_string).
    """
    key = _cache_key(optimised_params)

    # Fast path: already cached from a previous batch.
    cached = cache.get(key)
    if cached is not None:
        logger.debug("Cache hit for params", key=key)
        return cached

    # Per-key lock: only one coroutine evaluates a given param set.
    if key not in key_locks:
        key_locks[key] = asyncio.Lock()
    klock = key_locks[key]

    async with klock:
        # Re-check: another coroutine may have populated while we waited.
        cached = cache.get(key)
        if cached is not None:
            logger.debug("Cache hit after lock for params", key=key)
            return cached

        async with sem:
            wdk_error = ""
            wdk_result: ControlTestResult | None = None
            try:
                wdk_result = await run_positive_negative_controls(
                    request.config,
                    positive_controls=request.positive_controls,
                    negative_controls=request.negative_controls,
                )
            except AppError as trial_exc:
                wdk_error = str(trial_exc)
                wdk_result = None

            result_pair = (wdk_result, wdk_error)
            cache[key] = result_pair
            return result_pair


def _unpack_gather_result(
    raw_result: tuple[ControlTestResult | None, str] | BaseException,
    trial_num: int,
    params: dict[str, JSONValue],
) -> tuple[ControlTestResult | None, str]:
    """Unpack a result from asyncio.gather (may be an exception)."""
    if isinstance(raw_result, BaseException):
        wdk_error = str(raw_result)
        logger.warning(
            "WDK evaluation failed for trial",
            trial=trial_num,
            params=params,
            error=wdk_error,
        )
        return None, wdk_error
    wdk_result, wdk_error = raw_result
    if wdk_error:
        logger.warning(
            "WDK evaluation failed for trial",
            trial=trial_num,
            params=params,
            error=wdk_error,
        )
    return wdk_result, wdk_error
