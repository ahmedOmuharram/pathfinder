"""Tools for retrieving strategy results."""

from typing import Annotated

from kani import AIParam, ai_function

from veupath_chatbot.platform.errors import AppError, ErrorCode
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.tool_errors import tool_error
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.strategies.build import (
    get_result_count_for_site,
)
from veupath_chatbot.services.strategies.engine.validation import ValidationMixin

logger = get_logger(__name__)


class ExecutionTools(ValidationMixin):
    """Tools for retrieving strategy execution results."""

    @ai_function()
    async def get_result_count(
        self,
        wdk_step_id: Annotated[int, AIParam(desc="WDK step ID")],
        wdk_strategy_id: Annotated[
            int | None, AIParam(desc="WDK strategy ID (for imports)")
        ] = None,
    ) -> JSONObject:
        """Get the result count for a built step.

        For imported WDK strategies, provide wdk_strategy_id.
        """
        try:
            result = await get_result_count_for_site(
                self.session.site_id, wdk_step_id, wdk_strategy_id
            )
        except (AppError, OSError) as e:
            message = str(e)
            if wdk_strategy_id is None:
                message = f"{message} (try providing wdk_strategy_id)"
            return tool_error(ErrorCode.WDK_ERROR, message)
        return {"stepId": result.step_id, "count": result.count}
