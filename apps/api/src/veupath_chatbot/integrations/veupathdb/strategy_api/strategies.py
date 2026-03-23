"""Strategy CRUD methods for the Strategy API.

Provides :class:`StrategiesMixin` with methods to create, read, update,
and delete WDK strategies.
"""

import contextlib

import pydantic

from veupath_chatbot.integrations.veupathdb.strategy_api.base import StrategyAPIBase
from veupath_chatbot.integrations.veupathdb.strategy_api.helpers import (
    tag_internal_wdk_strategy_name,
)
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    WDKIdentifier,
    WDKStepTree,
    WDKStrategyDetails,
    WDKStrategySummary,
)
from veupath_chatbot.platform.errors import validate_response
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject

logger = get_logger(__name__)


class StrategiesMixin(StrategyAPIBase):
    """Mixin providing strategy CRUD methods."""

    async def create_strategy(  # noqa: PLR0913
        self,
        step_tree: WDKStepTree,
        name: str,
        description: str | None = None,
        *,
        is_public: bool = False,
        is_saved: bool = False,
        is_internal: bool = False,
        user_id: str | None = None,
    ) -> WDKIdentifier:
        """Create a strategy from a step tree.

        :param step_tree: Root of the step tree.
        :param name: Strategy name.
        :param description: Optional description.
        :param is_public: Whether the strategy is public.
        :param is_saved: Whether the strategy is saved.
        :param is_internal: Whether to tag as internal (Pathfinder helper).
        :param user_id: Optional explicit user ID override.
        :returns: WDK identifier with the created strategy ID.
        """
        if is_internal:
            name = tag_internal_wdk_strategy_name(name)
            is_public = False
            is_saved = False

        payload: JSONObject = {
            "name": name,
            "isPublic": is_public,
            "isSaved": is_saved,
            "stepTree": step_tree.model_dump(
                by_alias=True, exclude_none=True, mode="json"
            ),
        }
        if description:
            payload["description"] = description

        logger.info("Creating WDK strategy", name=name)

        uid = await self._get_user_id(user_id)
        raw = await self.client.post(
            f"/users/{uid}/strategies",
            json=payload,
        )
        return WDKIdentifier.model_validate(raw)

    async def get_strategy(
        self, strategy_id: int, user_id: str | None = None
    ) -> WDKStrategyDetails:
        """Get a strategy by ID."""
        uid = await self._get_user_id(user_id)
        raw = await self.client.get(f"/users/{uid}/strategies/{strategy_id}")
        return validate_response(
            WDKStrategyDetails, raw, f"WDK strategy response for {strategy_id}"
        )

    async def list_strategies(
        self, user_id: str | None = None
    ) -> list[WDKStrategySummary]:
        """List strategies for the current user."""
        uid = await self._get_user_id(user_id)
        raw = await self.client.get(f"/users/{uid}/strategies")
        if not isinstance(raw, list):
            return []
        result: list[WDKStrategySummary] = []
        for item in raw:
            if isinstance(item, dict):
                with contextlib.suppress(pydantic.ValidationError):
                    result.append(WDKStrategySummary.model_validate(item))
        return result

    async def list_public_strategies(self) -> list[WDKStrategySummary]:
        """List all public strategies from WDK.

        Endpoint: GET /strategy-lists/public
        No authentication required. Uses the same tolerant parsing as
        :meth:`list_strategies` — individual items that fail validation
        are silently skipped.
        """
        adapter = pydantic.TypeAdapter(list[WDKStrategySummary])
        raw = await self.client.get("/strategy-lists/public")
        try:
            return adapter.validate_python(raw)
        except pydantic.ValidationError:
            logger.warning("Failed to parse public strategies response")
            return []

    async def update_strategy(
        self,
        strategy_id: int,
        step_tree: WDKStepTree | None = None,
        name: str | None = None,
        user_id: str | None = None,
    ) -> WDKStrategyDetails:
        """Update a strategy."""
        uid = await self._get_user_id(user_id)

        if step_tree is not None:
            await self.client.put(
                f"/users/{uid}/strategies/{strategy_id}/step-tree",
                json={
                    "stepTree": step_tree.model_dump(
                        by_alias=True, exclude_none=True, mode="json"
                    )
                },
            )

        if name:
            await self.client.patch(
                f"/users/{uid}/strategies/{strategy_id}",
                json={"name": name},
            )

        # Return the updated strategy payload (best-effort).
        return await self.get_strategy(strategy_id, user_id=user_id)

    async def set_saved(
        self, strategy_id: int, *, is_saved: bool, user_id: str | None = None
    ) -> None:
        """Set the isSaved flag on a WDK strategy (draft vs saved)."""
        uid = await self._get_user_id(user_id)
        await self.client.patch(
            f"/users/{uid}/strategies/{strategy_id}",
            json={"isSaved": is_saved},
        )

    async def delete_strategy(
        self, strategy_id: int, user_id: str | None = None
    ) -> None:
        """Delete a strategy."""
        uid = await self._get_user_id(user_id)
        await self.client.delete(f"/users/{uid}/strategies/{strategy_id}")

    async def get_duplicated_step_tree(
        self, strategy_id: int, user_id: str | None = None
    ) -> WDKStepTree:
        """Get a duplicated step tree for a strategy.

        Matches monorepo's ``getDuplicatedStrategyStepTree`` which unwraps
        the ``stepTree`` wrapper from the response.

        :param strategy_id: WDK strategy ID to duplicate.
        :param user_id: Optional explicit user ID override.
        :returns: Duplicated step tree.
        """
        uid = await self._get_user_id(user_id)
        raw = await self.client.post(
            f"/users/{uid}/strategies/{strategy_id}/duplicated-step-tree",
            json={},
        )
        if isinstance(raw, dict) and "stepTree" in raw:
            return WDKStepTree.model_validate(raw["stepTree"])
        return WDKStepTree.model_validate(raw)
