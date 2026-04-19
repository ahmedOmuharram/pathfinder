"""Step filter CRUD operations for the Strategy API.

Provides :class:`FilterMixin` with methods to create and list
step filters via WDK's ``answerSpec.viewFilters`` mechanism.

WDK does NOT have dedicated filter endpoints (``/filter``, ``/filter/{name}``).
Filters are managed by reading/patching the step's ``answerSpec.viewFilters``
array through the step resource itself.
"""

from pydantic import JsonValue

from pathfinder.integrations.veupathdb.strategy_api.base import StrategyAPIBase
from pathfinder.integrations.veupathdb.wdk_models import WDKFilterValue


class FilterMixin(StrategyAPIBase):
    """Mixin providing step filter CRUD via answerSpec.viewFilters."""

    async def list_step_filters(
        self, step_id: int, user_id: str | None = None
    ) -> list[WDKFilterValue]:
        """List viewFilters for a step.

        Reads the step resource and extracts ``searchConfig.viewFilters``.
        """
        uid = await self._get_user_id(user_id)
        return await self.client.get_step_view_filters(uid, step_id)

    async def set_step_filter(
        self,
        step_id: int,
        filter_name: str,
        value: JsonValue,
        *,
        disabled: bool = False,
        user_id: str | None = None,
    ) -> None:
        """Create or update a viewFilter on a step.

        Reads the current viewFilters, replaces or appends the named filter,
        then PATCHes the step with the updated array.
        """
        uid = await self._get_user_id(user_id)
        current = await self.client.get_step_view_filters(uid, step_id)
        updated: list[WDKFilterValue] = [f for f in current if f.name != filter_name]
        new_filter = WDKFilterValue(
            name=filter_name,
            value=value,
            disabled=disabled,
        )
        updated.append(new_filter)
        await self.client.update_step_view_filters(uid, step_id, updated)
