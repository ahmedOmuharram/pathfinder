"""Module-level helpers for WDK strategy operations.

Contains :class:`StepTreeNode` for building step trees, internal strategy
name tagging utilities, and shared constants.
"""

from __future__ import annotations

from veupath_chatbot.integrations.veupathdb.client import VEuPathDBClient
from veupath_chatbot.platform.types import JSONObject

# Internal (Pathfinder-created) WDK strategies.
#
# WDK doesn't support arbitrary metadata on a strategy. To reliably identify
# "internal helper" strategies (step counts, etc.) later, we tag the WDK name
# with a reserved prefix. This avoids incorrectly treating *all* unsaved
# strategies (`isSaved=false`) as internal.
PATHFINDER_INTERNAL_STRATEGY_NAME_PREFIX = "__pathfinder_internal__:"

# Use current user session (guest or authenticated)
CURRENT_USER = "current"


def is_internal_wdk_strategy_name(name: str | None) -> bool:
    """Check if a WDK strategy name is a Pathfinder internal helper strategy.

    Internal strategies are used for control tests and step counts.
    They are tagged with ``__pathfinder_internal__:`` prefix.

    :param name: WDK strategy name or None.
    :returns: True if the name indicates an internal strategy.
    """
    return bool(name) and str(name).startswith(PATHFINDER_INTERNAL_STRATEGY_NAME_PREFIX)


def tag_internal_wdk_strategy_name(name: str) -> str:
    """Add the internal strategy name prefix if not already present."""
    if name.startswith(PATHFINDER_INTERNAL_STRATEGY_NAME_PREFIX):
        return name
    return f"{PATHFINDER_INTERNAL_STRATEGY_NAME_PREFIX}{name}"


def strip_internal_wdk_strategy_name(name: str) -> str:
    """Remove the internal strategy name prefix if present.

    :param name: WDK strategy name (may include internal prefix).
    :returns: Display name without the ``__pathfinder_internal__:`` prefix.
    """
    if name.startswith(PATHFINDER_INTERNAL_STRATEGY_NAME_PREFIX):
        return name[len(PATHFINDER_INTERNAL_STRATEGY_NAME_PREFIX) :]
    return name


async def resolve_wdk_user_id(client: VEuPathDBClient) -> str | None:
    """Resolve the concrete WDK user ID from a ``/users/current`` call.

    Some WDK deployments reject mutations on ``/users/current/...``.
    This helper resolves the actual numeric user ID once so callers
    can use ``/users/{userId}/...`` for all subsequent requests.

    :returns: Resolved user ID string, or ``None`` if resolution failed.
    """
    me = await client.get("/users/current")
    if isinstance(me, dict):
        candidate = me.get("id")
        if candidate is not None:
            return str(candidate)
    return None


class StepTreeNode:
    """Node in a step tree (for building strategy).

    Represents a single step with optional primary (and for combines, secondary)
    input references. Used to build the ``stepTree`` payload for WDK strategy
    creation.
    """

    def __init__(
        self,
        step_id: int,
        primary_input: StepTreeNode | None = None,
        secondary_input: StepTreeNode | None = None,
    ) -> None:
        """Build a step tree node.

        :param step_id: WDK step ID (integer from create_step).
        :param primary_input: Child node for unary/binary operations.
        :param secondary_input: Second child for combine (e.g. UNION) steps.
        """
        self.step_id = step_id
        self.primary_input = primary_input
        self.secondary_input = secondary_input

    def to_dict(self) -> JSONObject:
        """Convert to WDK stepTree format."""
        result: JSONObject = {"stepId": self.step_id}
        if self.primary_input:
            result["primaryInput"] = self.primary_input.to_dict()
        if self.secondary_input:
            result["secondaryInput"] = self.secondary_input.to_dict()
        return result
