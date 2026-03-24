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
    GraphSnapshotContent,
    GraphSnapshotEventData,
    StrategyUpdateEventData,
    SubKaniTaskEndEventData,
)
from veupath_chatbot.platform.types import JSONArray
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
    created_steps: JSONArray,
    emitted_step_ids: set[str],
    graph: StrategyGraph | None,
    graph_id: str | None,
    emit_event: EmitEvent,
) -> None:
    """Emit strategy_update and graph_snapshot events for newly created steps."""
    if graph is None:
        return

    for step_value in created_steps:
        if not isinstance(step_value, dict):
            continue
        step = step_value
        step_id_raw = step.get("stepId")
        step_id = step_id_raw if isinstance(step_id_raw, str) else None
        if not step_id or step_id in emitted_step_ids:
            continue
        emitted_step_ids.add(step_id)
        graph_id_raw = step.get("graphId")
        graph_id_str = graph_id_raw if isinstance(graph_id_raw, str) else graph_id
        await emit_event(
            {
                "type": "strategy_update",
                "data": StrategyUpdateEventData(
                    graph_id=graph_id_str,
                    step=step,
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
        snapshot_raw = step.get("graphSnapshot")
        snapshot = snapshot_raw if isinstance(snapshot_raw, dict) else None
        if snapshot:
            await emit_event(
                {
                    "type": "graph_snapshot",
                    "data": GraphSnapshotEventData(
                        graph_snapshot=GraphSnapshotContent.model_validate(snapshot),
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
