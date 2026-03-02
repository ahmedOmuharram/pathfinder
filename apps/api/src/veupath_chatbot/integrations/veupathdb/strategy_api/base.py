"""StrategyAPI base class with shared infrastructure.

Provides initialization, parameter normalization, and session management
that all mixin classes depend on.
"""

from __future__ import annotations

from veupath_chatbot.integrations.veupathdb.client import VEuPathDBClient
from veupath_chatbot.integrations.veupathdb.param_utils import normalize_param_value
from veupath_chatbot.integrations.veupathdb.strategy_api.helpers import CURRENT_USER
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject

logger = get_logger(__name__)


class StrategyAPIBase:
    """Base infrastructure for :class:`StrategyAPI`.

    Provides ``__init__``, parameter normalization, and WDK session management.
    Mixin classes inherit from this to access shared state.
    """

    def __init__(self, client: VEuPathDBClient, user_id: str = CURRENT_USER) -> None:
        """Initialize the strategy API.

        :param client: VEuPathDB HTTP client (site-specific).
        :param user_id: WDK user ID; defaults to ``"current"`` (resolved at first use).
        """
        self.client = client
        self.user_id = user_id
        self._session_initialized = False
        self._boolean_search_cache: dict[str, str] = {}
        self._answer_param_cache: dict[str, set[str]] = {}

    def _normalize_parameters(
        self,
        parameters: JSONObject,
        *,
        keep_empty: set[str] | None = None,
    ) -> dict[str, str]:
        """Normalize parameters to WDK string values; omit empty values.

        WDK rejects params like ``hard_floor`` with value ``""`` (Cannot be empty).
        Omitting empty params avoids 422s when a required param is left blank
        in the UI; the caller should supply a valid value for required params.

        :param parameters: Raw parameter dict.
        :param keep_empty: Param names that must be kept even when empty
            (e.g. AnswerParams that WDK requires as ``""``).
        """
        keep = keep_empty or set()
        out: dict[str, str] = {}
        for key, value in (parameters or {}).items():
            s = normalize_param_value(value)
            if s.strip() or key in keep:
                out[key] = s if s.strip() else ""
        return out

    async def _ensure_session(self) -> None:
        """Initialize session and resolve user id for mutation endpoints.

        Some WDK deployments allow GET/POST using `/users/current/...` but do NOT
        allow PUT/PATCH/DELETE on `/users/current/...` (405 Method Not Allowed).
        Resolve the concrete user id once and then use `/users/{userId}/...`.
        """
        if self._session_initialized:
            return
        me = await self.client.get("/users/current")
        resolved_user_id: str | None = None
        if isinstance(me, dict):
            # WDK UserFormatter emits the user ID under JsonKeys.ID = "id".
            candidate = me.get("id")
            if candidate is not None:
                resolved_user_id = str(candidate)

        # Only override when we were using the placeholder "current".
        if self.user_id == CURRENT_USER and resolved_user_id:
            logger.info(
                "Resolved WDK user id for mutations",
                resolved_user_id=resolved_user_id,
            )
            self.user_id = resolved_user_id
        self._session_initialized = True
