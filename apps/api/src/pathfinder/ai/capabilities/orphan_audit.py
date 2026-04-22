from __future__ import annotations

from dataclasses import dataclass

from pydantic_ai.capabilities.abstract import (
    AbstractCapability,
    CapabilityOrdering,
)
from pydantic_ai.messages import (
    RetryPromptPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models import ModelRequestContext
from pydantic_ai.tools import RunContext

from pathfinder.ai.agents._history_processor import pair_tool_calls
from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.platform.logging import get_logger

logger = get_logger(__name__)


@dataclass
class OrphanToolAuditor(AbstractCapability[AgentDeps]):
    """Last-mile sweep for unpaired tool_call_id / tool_return_id.

    Registered with ``position='innermost'`` so it runs AFTER every other
    capability in the chain — the last transform before the model wire.
    Every orphan here is a bug: ``history_processors=[pair_tool_calls]``
    already fires on the same request. If this capability repairs an
    orphan, we log an ``error`` so the root cause gets flagged.
    """

    def get_ordering(self) -> CapabilityOrdering:
        return CapabilityOrdering(position="innermost")

    async def before_model_request(
        self,
        ctx: RunContext[AgentDeps],
        request_context: ModelRequestContext,
    ) -> ModelRequestContext:
        messages = request_context.messages
        call_ids: set[str] = set()
        satisfied_ids: set[str] = set()
        for msg in messages:
            for part in msg.parts:
                if isinstance(part, ToolCallPart):
                    call_ids.add(part.tool_call_id)
                elif isinstance(part, ToolReturnPart) or (
                    isinstance(part, RetryPromptPart) and part.tool_call_id
                ):
                    satisfied_ids.add(part.tool_call_id)
        orphan_calls = call_ids - satisfied_ids
        orphan_returns = satisfied_ids - call_ids
        if orphan_calls or orphan_returns:
            logger.error(
                "orphan tool ids reached model wire — repairing",
                orphan_calls=sorted(orphan_calls),
                orphan_returns=sorted(orphan_returns),
                conversation_id=str(getattr(ctx.deps, "conversation_id", "")),
            )
            request_context.messages = pair_tool_calls(list(messages))
        return request_context
