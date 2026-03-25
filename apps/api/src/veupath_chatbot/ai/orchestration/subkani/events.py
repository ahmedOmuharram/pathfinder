"""SSE event emission for sub-kani orchestration.

Handles emitting strategy_update, graph_snapshot, and subkani_task_end
events during sub-kani execution.
"""

from dataclasses import dataclass

from veupath_chatbot.ai.models.pricing import estimate_cost
from veupath_chatbot.ai.orchestration.delegation import CompiledCombine, CompiledTask
from veupath_chatbot.ai.orchestration.results import NodeResult
from veupath_chatbot.ai.orchestration.subkani.utils import SubKaniRoundResult
from veupath_chatbot.ai.orchestration.types import EmitEvent
from veupath_chatbot.domain.strategy.session import StrategyGraph
from veupath_chatbot.platform.event_schemas import (
    StrategyUpdateEventData,
    SubKaniTaskEndEventData,
)
from veupath_chatbot.services.strategies.schemas import StepResponse


@dataclass
class DelegationRunData:
    """Aggregated data from a delegation run for response construction."""

    graph: StrategyGraph | None
    graph_id: str | None
    graph_name: str
    graph_description: str
    normalized: list[CompiledTask]
    normalized_combines: list[CompiledCombine]
    results: list[NodeResult]
    start: float


async def _emit_step_events(
    *,
    created_steps: list[StepResponse],
    emitted_step_ids: set[str],
    graph: StrategyGraph | None,
    graph_id: str | None,
    emit_event: EmitEvent,
) -> None:
    """Emit strategy_update and graph_snapshot events for newly created steps."""
    if graph is None:
        return

    for step in created_steps:
        if step.id in emitted_step_ids:
            continue
        emitted_step_ids.add(step.id)
        step_dict = step.model_dump(by_alias=True, exclude_none=True)
        await emit_event(
            {
                "type": "strategy_update",
                "data": StrategyUpdateEventData(
                    graph_id=graph_id,
                    step=step_dict,
                    all_steps=[
                        StepResponse(
                            id=sid,
                            kind=s.infer_kind(),
                            display_name=s.display_name or s.search_name,
                        ).model_dump(by_alias=True, exclude_none=True)
                        for sid, s in graph.steps.items()
                    ],
                ).model_dump(by_alias=True, exclude_none=True),
            }
        )


async def _emit_task_end(
    *,
    task: str,
    subkani_model_id: str,
    emit_event: EmitEvent,
    round_result: SubKaniRoundResult | None = None,
    status: str = "done",
) -> None:
    """Emit a subkani_task_end event with token usage."""
    sub_cost = estimate_cost(
        subkani_model_id,
        prompt_tokens=round_result.prompt_tokens if round_result else 0,
        completion_tokens=round_result.completion_tokens if round_result else 0,
    )
    await emit_event(
        {
            "type": "subkani_task_end",
            "data": SubKaniTaskEndEventData(
                task=task,
                status=status,
                model_id=subkani_model_id,
                prompt_tokens=round_result.prompt_tokens if round_result else 0,
                completion_tokens=round_result.completion_tokens if round_result else 0,
                llm_call_count=round_result.llm_call_count if round_result else 0,
                estimated_cost_usd=sub_cost,
            ).model_dump(by_alias=True),
        }
    )
