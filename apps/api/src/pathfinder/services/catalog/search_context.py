"""Narrows a search's parameters with the values already bound to it."""

from __future__ import annotations

from pathfinder.integrations.veupathdb.client import VEuPathDBClient
from pathfinder.integrations.veupathdb.wdk_models import WDKSearchResponse
from pathfinder.platform.errors import AppError
from pathfinder.platform.logging import get_logger

logger = get_logger(__name__)


async def get_search_params_under_context(
    client: VEuPathDBClient,
    record_type: str,
    search_name: str,
    context: dict[str, str],
) -> WDKSearchResponse:
    """A search's parameters, narrowed by ``context`` when WDK can narrow them.

    Narrowing replaces a dependent param's static vocabulary with the one valid
    under its parents. WDK can refuse to narrow a value it accepts on the run
    endpoint, so a refusal costs vocabulary precision and never the search.

    Raises only when the static view is unreachable too.
    """
    if not context:
        return await client.get_search_details(
            record_type, search_name, expand_params=True
        )
    try:
        return await client.get_search_details_with_params(
            record_type, search_name, context=context, expand_params=True
        )
    except AppError as exc:
        logger.warning(
            "WDK could not contextualize search params; using the static view",
            search=search_name,
            record_type=record_type,
            context_params=sorted(context),
            error=str(exc),
        )
        return await client.get_search_details(
            record_type, search_name, expand_params=True
        )
