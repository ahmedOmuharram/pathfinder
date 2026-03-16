"""Cost estimation utilities for LLM model usage."""

from veupath_chatbot.ai.models.catalog import get_model_entry
from veupath_chatbot.platform.logging import get_logger

logger = get_logger(__name__)


def estimate_cost(
    model_id: str,
    prompt_tokens: int,
    completion_tokens: int,
    cached_tokens: int = 0,
) -> float:
    """Estimate USD cost for a model call.

    Cached tokens are charged at cached_input_price instead of input_price.
    Returns 0.0 and logs a warning for unknown models.
    """
    entry = get_model_entry(model_id)
    if not entry:
        logger.warning("Unknown model for cost estimation", model_id=model_id)
        return 0.0
    uncached_input = prompt_tokens - cached_tokens
    input_cost = (uncached_input / 1_000_000) * entry.input_price
    cached_cost = (cached_tokens / 1_000_000) * entry.cached_input_price
    output_cost = (completion_tokens / 1_000_000) * entry.output_price
    return round(input_cost + cached_cost + output_cost, 6)
