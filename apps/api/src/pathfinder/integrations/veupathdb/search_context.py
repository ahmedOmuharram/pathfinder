from __future__ import annotations

from pathfinder.integrations.veupathdb._searches import SearchEndpoints
from pathfinder.integrations.veupathdb.wdk_models import WDKSearchResponse
from pathfinder.platform.errors import AppError
from pathfinder.platform.logging import get_logger

logger = get_logger(__name__)


async def get_search_params_under_context(
    client: SearchEndpoints,
    record_type: str,
    search_name: str,
    context: dict[str, str],
) -> WDKSearchResponse:
    """A search's parameters, narrowed by ``context`` when WDK can narrow them.

    Contextualizing is an **enrichment**: it replaces a dependent param's
    static vocabulary with the one valid under its parents. It is not a
    precondition for the parent values being valid, and WDK does not treat it
    as one -- measured on live PlasmoDB, ``GenesByOrthologPattern`` answers 500
    to this endpoint for an organism value it accepts and executes on the run
    endpoint (``totalCount`` 3347).

    So a failure here costs vocabulary precision, never the search. Callers used
    to decide that for themselves: six sites, four different exception types
    caught, five different recoveries, and two with no handling at all. The two
    with none are where the bugs landed -- one of them abandoned a criterion and
    with it a 16-step strategy.

    Raises only when the static view is unreachable too, which is a real outage
    rather than a narrowing we can do without.
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
