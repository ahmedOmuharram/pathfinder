"""Strategy CRUD methods for the Strategy API.

Provides :class:`StrategiesMixin` with methods to create, read, update,
and delete WDK strategies.
"""

import contextlib
from typing import cast

import pydantic

from veupath_chatbot.domain.strategy.ast import StepTreeNode
from veupath_chatbot.integrations.veupathdb.strategy_api.base import StrategyAPIBase
from veupath_chatbot.integrations.veupathdb.strategy_api.helpers import (
    tag_internal_wdk_strategy_name,
)
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    WDKStrategyDetails,
    WDKStrategySummary,
)
from veupath_chatbot.platform.errors import DataParsingError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject

logger = get_logger(__name__)


class StrategiesMixin(StrategyAPIBase):
    """Mixin providing strategy CRUD methods."""

    async def create_strategy(
        self,
        step_tree: StepTreeNode,
        name: str,
        description: str | None = None,
        *,
        is_public: bool = False,
        is_saved: bool = False,
        is_internal: bool = False,
    ) -> JSONObject:
        """Create a strategy from a step tree.

        :param step_tree: Root of the step tree.
        :param name: Strategy name.
        :param description: Optional description.
        :param is_public: Whether the strategy is public.
        :param is_saved: Whether the strategy is saved.
        :param is_internal: Whether to tag as internal (Pathfinder helper).
        :returns: Created strategy data.
        """
        if is_internal:
            name = tag_internal_wdk_strategy_name(name)
            is_public = False
            is_saved = False

        payload: JSONObject = {
            "name": name,
            "isPublic": is_public,
            "isSaved": is_saved,
            "stepTree": step_tree.to_dict(),
        }
        if description:
            payload["description"] = description

        logger.info("Creating WDK strategy", name=name)

        await self._ensure_session()
        return cast(
            "JSONObject",
            await self.client.post(
                f"/users/{self.user_id}/strategies",
                json=payload,
            ),
        )

    async def get_strategy(self, strategy_id: int) -> WDKStrategyDetails:
        """Get a strategy by ID."""
        await self._ensure_session()
        raw = await self.client.get(f"/users/{self.user_id}/strategies/{strategy_id}")
        try:
            return WDKStrategyDetails.model_validate(raw)
        except pydantic.ValidationError as e:
            msg = f"Unexpected WDK strategy response for {strategy_id}: {e}"
            raise DataParsingError(msg) from e

    async def list_strategies(self) -> list[WDKStrategySummary]:
        """List strategies for the current user."""
        await self._ensure_session()
        raw = await self.client.get(f"/users/{self.user_id}/strategies")
        if not isinstance(raw, list):
            return []
        result: list[WDKStrategySummary] = []
        for item in raw:
            if isinstance(item, dict):
                with contextlib.suppress(pydantic.ValidationError):
                    result.append(WDKStrategySummary.model_validate(item))
        return result

    async def update_strategy(
        self,
        strategy_id: int,
        step_tree: StepTreeNode | None = None,
        name: str | None = None,
    ) -> WDKStrategyDetails:
        """Update a strategy."""
        await self._ensure_session()

        if step_tree is not None:
            await self.client.put(
                f"/users/{self.user_id}/strategies/{strategy_id}/step-tree",
                json={"stepTree": step_tree.to_dict()},
            )

        if name:
            await self.client.patch(
                f"/users/{self.user_id}/strategies/{strategy_id}",
                json={"name": name},
            )

        # Return the updated strategy payload (best-effort).
        return await self.get_strategy(strategy_id)

    async def set_saved(self, strategy_id: int, *, is_saved: bool) -> None:
        """Set the isSaved flag on a WDK strategy (draft vs saved)."""
        await self._ensure_session()
        await self.client.patch(
            f"/users/{self.user_id}/strategies/{strategy_id}",
            json={"isSaved": is_saved},
        )

    async def delete_strategy(self, strategy_id: int) -> None:
        """Delete a strategy."""
        await self._ensure_session()
        await self.client.delete(f"/users/{self.user_id}/strategies/{strategy_id}")
