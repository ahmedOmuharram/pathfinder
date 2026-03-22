"""Step filter CRUD operations for the Strategy API.

Provides :class:`FilterMixin` with methods to create, delete, and list
step filters via WDK's ``answerSpec.viewFilters`` mechanism.

WDK does NOT have dedicated filter endpoints (``/filter``, ``/filter/{name}``).
Filters are managed by reading/patching the step's ``answerSpec.viewFilters``
array through the step resource itself.
"""

from veupath_chatbot.integrations.veupathdb.strategy_api.base import StrategyAPIBase
from veupath_chatbot.platform.types import JSONArray, JSONValue


class FilterMixin(StrategyAPIBase):
    """Mixin providing step filter CRUD via answerSpec.viewFilters."""

    async def list_step_filters(
        self, step_id: int, user_id: str | None = None
    ) -> JSONArray:
        """List viewFilters for a step.

        Reads the step resource and extracts ``answerSpec.viewFilters``.
        """
        uid = await self._get_user_id(user_id)
        return await self.client.get_step_view_filters(uid, step_id)

    async def set_step_filter(
        self,
        step_id: int,
        filter_name: str,
        value: JSONValue,
        *,
        disabled: bool = False,
        user_id: str | None = None,
    ) -> JSONValue:
        """Create or update a viewFilter on a step.

        Reads the current viewFilters, replaces or appends the named filter,
        then PATCHes the step with the updated array.
        """
        uid = await self._get_user_id(user_id)
        current = await self.client.get_step_view_filters(uid, step_id)
        updated: JSONArray = [
            f for f in current if isinstance(f, dict) and f.get("name") != filter_name
        ]
        new_filter: JSONValue = {
            "name": filter_name,
            "value": value,
            "disabled": disabled,
        }
        updated.append(new_filter)
        return await self.client.update_step_view_filters(uid, step_id, updated)

    async def delete_step_filter(
        self, step_id: int, filter_name: str, user_id: str | None = None
    ) -> JSONValue:
        """Remove a viewFilter from a step.

        Reads the current viewFilters, removes the named filter, then PATCHes
        the step with the updated array.
        """
        uid = await self._get_user_id(user_id)
        current = await self.client.get_step_view_filters(uid, step_id)
        updated: JSONArray = [
            f for f in current if isinstance(f, dict) and f.get("name") != filter_name
        ]
        return await self.client.update_step_view_filters(uid, step_id, updated)
