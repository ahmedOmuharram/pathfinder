"""finalize() logic: persist plans, snapshots, commit."""

from __future__ import annotations

from sqlalchemy.exc import SQLAlchemyError

from veupath_chatbot.domain.strategy.ast import from_dict
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.services.strategies.serialization import (
    build_steps_data_from_graph_snapshot,
    build_steps_data_from_plan,
)

from .message_builder import build_and_persist_messages
from .sse import sse_event
from .utils import parse_uuid

logger = get_logger(__name__)


async def finalize(proc) -> list[str]:
    """Finalize the stream: persist messages + snapshots, and return extra SSE lines."""
    extra_events: list[str] = []

    await proc.maybe_flush_thinking(force=True)
    await proc.strategy_repo.clear_thinking(proc.strategy.id)

    await build_and_persist_messages(
        strategy_repo=proc.strategy_repo,
        strategy_id=proc.strategy.id,
        assistant_messages=proc.assistant_messages,
        citations=proc.citations,
        planning_artifacts=proc.planning_artifacts,
        reasoning=proc.reasoning,
        optimization_progress=proc.optimization_progress,
        tool_calls=proc.tool_calls,
        subkani_calls=proc.subkani_calls,
        subkani_status=proc.subkani_status,
    )

    if proc.latest_plans:
        for graph_id, payload in proc.latest_plans.items():
            graph_uuid = parse_uuid(graph_id) or proc.strategy.id
            latest_plan = payload.get("plan")
            name_value = payload.get("name")
            latest_name = (
                str(name_value) if isinstance(name_value, str) else "Draft Strategy"
            )
            record_type_value = payload.get("recordType")
            latest_record_type = (
                str(record_type_value) if isinstance(record_type_value, str) else None
            )
            description_value = payload.get("description")
            latest_description = (
                str(description_value) if isinstance(description_value, str) else None
            )
            snapshot = proc.latest_graph_snapshots.get(graph_id)
            if not latest_plan:
                continue

            if latest_description is not None and isinstance(latest_plan, dict):
                metadata = latest_plan.get("metadata")
                if not isinstance(metadata, dict):
                    metadata = {}
                metadata["description"] = latest_description
                latest_plan["metadata"] = metadata

            try:
                # Prefer plan-derived steps; use snapshot only when plan is missing.
                if isinstance(latest_plan, dict):
                    steps_data = build_steps_data_from_plan(latest_plan)
                elif isinstance(snapshot, dict) and snapshot.get("steps"):
                    steps_data = build_steps_data_from_graph_snapshot(snapshot)
                else:
                    steps_data = []

                if isinstance(snapshot, dict):
                    name_snapshot = snapshot.get("name")
                    graph_name_snapshot = snapshot.get("graphName")
                    if isinstance(name_snapshot, str):
                        latest_name = name_snapshot
                    elif isinstance(graph_name_snapshot, str):
                        latest_name = graph_name_snapshot
                    record_type_snapshot = snapshot.get("recordType")
                    if isinstance(record_type_snapshot, str):
                        latest_record_type = record_type_snapshot
                    description_snapshot = snapshot.get("description")
                    if isinstance(description_snapshot, str):
                        latest_description = description_snapshot
                    root_step_id_value = snapshot.get("rootStepId")
                    root_step_id = (
                        str(root_step_id_value)
                        if isinstance(root_step_id_value, str)
                        else None
                    )
                else:
                    root_step_id = None

                # Try plan persistence first; if the plan can't be parsed/validated yet,
                # fall back to snapshot-derived steps persistence so refresh won't lose the graph.
                try:
                    if isinstance(latest_plan, dict):
                        strategy_ast = from_dict(latest_plan)
                        canonical_plan = strategy_ast.to_dict()
                    else:
                        canonical_plan = None
                except Exception:
                    canonical_plan = None

                if canonical_plan is not None:
                    updated = await proc.strategy_repo.update(
                        strategy_id=graph_uuid,
                        name=latest_name,
                        title=latest_name,
                        plan=canonical_plan,
                        record_type=latest_record_type,
                    )
                    if not updated:
                        await proc.strategy_repo.create(
                            user_id=proc.user_id,
                            name=latest_name,
                            title=latest_name,
                            site_id=proc.site_id,
                            record_type=latest_record_type,
                            plan=canonical_plan,
                            strategy_id=graph_uuid,
                        )
                else:
                    updated = await proc.strategy_repo.update(
                        strategy_id=graph_uuid,
                        name=latest_name,
                        title=latest_name,
                        record_type=latest_record_type,
                        steps=steps_data,
                        root_step_id=root_step_id,
                        root_step_id_set=True,
                    )
                    if not updated:
                        await proc.strategy_repo.create(
                            user_id=proc.user_id,
                            name=latest_name,
                            title=latest_name,
                            site_id=proc.site_id,
                            record_type=latest_record_type,
                            plan={},
                            steps=steps_data,
                            root_step_id=root_step_id,
                            strategy_id=graph_uuid,
                        )
                if graph_uuid == proc.strategy.id:
                    await proc.strategy_repo.update(
                        strategy_id=proc.strategy.id,
                        title=latest_name,
                    )

                pending = proc.pending_strategy_link.get(graph_id)
                if pending:
                    wdk_strategy_id_value = pending.get("wdkStrategyId")
                    wdk_strategy_id: int | None = None
                    if wdk_strategy_id_value is not None:
                        if isinstance(wdk_strategy_id_value, int):
                            wdk_strategy_id = wdk_strategy_id_value
                        elif isinstance(wdk_strategy_id_value, (str, float)):
                            try:
                                wdk_strategy_id = int(wdk_strategy_id_value)
                            except ValueError, TypeError:
                                wdk_strategy_id = None
                    if wdk_strategy_id is not None:
                        await proc.strategy_repo.update(
                            strategy_id=graph_uuid,
                            wdk_strategy_id=wdk_strategy_id,
                            wdk_strategy_id_set=True,
                        )
                    pending = {**pending, "strategySnapshotId": str(graph_uuid)}
                    extra_events.append(sse_event("strategy_link", pending))
            except (SQLAlchemyError, ValueError) as e:
                logger.error(
                    "Failed to save strategy snapshot",
                    error=str(e),
                    graph_id=graph_id,
                    exc_info=True,
                )

    if proc.latest_graph_snapshots:
        for graph_id, snapshot in proc.latest_graph_snapshots.items():
            if graph_id in proc.latest_plans or not isinstance(snapshot, dict):
                continue
            graph_uuid = parse_uuid(graph_id) or proc.strategy.id
            steps_data = build_steps_data_from_graph_snapshot(snapshot)
            if not steps_data:
                continue
            root_step_id_value = snapshot.get("rootStepId")
            root_step_id = (
                str(root_step_id_value) if isinstance(root_step_id_value, str) else None
            )
            record_type_value = snapshot.get("recordType")
            record_type = (
                str(record_type_value) if isinstance(record_type_value, str) else None
            )
            graph_name_value = snapshot.get("graphName")
            name_value = snapshot.get("name")
            name = (
                str(graph_name_value)
                if isinstance(graph_name_value, str)
                else (str(name_value) if isinstance(name_value, str) else None)
            )
            updated = await proc.strategy_repo.update(
                strategy_id=graph_uuid,
                name=name,
                title=name,
                record_type=record_type,
                steps=steps_data,
                root_step_id=root_step_id,
                root_step_id_set=True,
            )
            if not updated:
                name_str = name or "Draft Strategy"
                await proc.strategy_repo.create(
                    user_id=proc.user_id,
                    name=name_str,
                    title=name_str,
                    site_id=proc.site_id,
                    record_type=record_type,
                    plan={},
                    steps=steps_data,
                    root_step_id=root_step_id,
                    strategy_id=graph_uuid,
                )
            if graph_uuid == proc.strategy.id:
                name_str = name or "Draft Strategy"
                await proc.strategy_repo.update(
                    strategy_id=proc.strategy.id,
                    title=name_str,
                )

    return extra_events
