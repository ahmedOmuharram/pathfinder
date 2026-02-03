"""Chat stream event processing + persistence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.persistence.models import Strategy
from veupath_chatbot.persistence.repo import StrategyRepository
from veupath_chatbot.domain.strategy.ast import from_dict
from veupath_chatbot.services.strategies.serialization import (
    build_steps_data_from_graph_snapshot,
    build_steps_data_from_plan,
)

from .events import (
    GRAPH_CLEARED,
    GRAPH_DELETED,
    GRAPH_PLAN,
    GRAPH_SNAPSHOT,
    STRATEGY_LINK,
)
from .sse import sse_event, sse_error, sse_message_start
from .thinking import build_thinking_payload, normalize_subkani_activity, normalize_tool_calls
from .utils import parse_uuid

logger = get_logger(__name__)


class ChatStreamProcessor:
    """Stateful processor for a single streamed chat turn."""

    def __init__(
        self,
        *,
        strategy_repo: StrategyRepository,
        site_id: str,
        user_id: UUID,
        strategy: Strategy,
        auth_token: str,
        strategy_payload: dict[str, Any],
    ) -> None:
        self.strategy_repo = strategy_repo
        self.site_id = site_id
        self.user_id = user_id
        self.strategy = strategy
        self.auth_token = auth_token
        self.strategy_payload = strategy_payload

        self.assistant_messages: list[str] = []
        self.tool_calls: list[dict[str, Any]] = []
        self.tool_calls_by_id: dict[str, dict[str, Any]] = {}
        self.subkani_calls: dict[str, list[dict[str, Any]]] = {}
        self.subkani_calls_by_id: dict[str, tuple[str, dict[str, Any]]] = {}
        self.subkani_status: dict[str, str] = {}
        self.latest_plans: dict[str, dict[str, Any]] = {}
        self.latest_graph_snapshots: dict[str, dict[str, Any]] = {}
        self.pending_strategy_link: dict[str, dict[str, Any]] = {}

        self.last_thinking_flush = datetime.now(timezone.utc)
        self.thinking_dirty = False
        self.thinking_flush_interval = 2.0

    def resolve_graph_id(self, raw_id: str | None) -> str | None:
        # Current implementation is single-graph; preserve behavior.
        del raw_id
        return str(self.strategy.id)

    async def maybe_flush_thinking(self, *, force: bool = False) -> None:
        if not self.thinking_dirty:
            return
        now = datetime.now(timezone.utc)
        if not force:
            elapsed = (now - self.last_thinking_flush).total_seconds()
            if elapsed < self.thinking_flush_interval:
                return
        payload = build_thinking_payload(
            self.tool_calls_by_id, self.subkani_calls, self.subkani_status
        )
        await self.strategy_repo.update_thinking(self.strategy.id, payload)
        self.last_thinking_flush = now
        self.thinking_dirty = False

    def start_event(self) -> str:
        return sse_message_start(
            strategy_id=str(self.strategy.id),
            strategy=self.strategy_payload,
            auth_token=self.auth_token,
        )

    async def on_event(self, event_type: str, event_data: dict[str, Any]) -> str | None:
        """Process one semantic event; returns SSE line (or None if skipped)."""
        if event_type == "message_start":
            return None

        if event_type == "assistant_message":
            content = event_data.get("content", "")
            if content:
                self.assistant_messages.append(content)

        elif event_type == GRAPH_SNAPSHOT:
            snapshot = event_data.get("graphSnapshot")
            if isinstance(snapshot, dict):
                graph_id = self.resolve_graph_id(snapshot.get("graphId"))
                if graph_id:
                    snapshot["graphId"] = graph_id
                    event_data["graphSnapshot"] = snapshot
                    self.latest_graph_snapshots[str(graph_id)] = snapshot

        elif event_type == GRAPH_PLAN:
            graph_id = self.resolve_graph_id(event_data.get("graphId"))
            if graph_id:
                self.latest_plans[str(graph_id)] = {
                    "plan": event_data.get("plan"),
                    "name": event_data.get("name"),
                    "recordType": event_data.get("recordType"),
                    "description": event_data.get("description"),
                }

        elif event_type == GRAPH_CLEARED:
            graph_id = self.resolve_graph_id(event_data.get("graphId"))
            graph_uuid = parse_uuid(graph_id)
            if graph_uuid:
                await self.strategy_repo.update(
                    strategy_id=graph_uuid,
                    title="Draft Strategy",
                    plan={},
                    record_type=None,
                    wdk_strategy_id=None,
                )

        elif event_type == GRAPH_DELETED:
            graph_id = self.resolve_graph_id(event_data.get("graphId"))
            graph_uuid = parse_uuid(graph_id)
            if graph_uuid:
                await self.strategy_repo.update(
                    strategy_id=graph_uuid,
                    title=None,
                    plan={},
                    record_type=None,
                    wdk_strategy_id=None,
                    wdk_strategy_id_set=True,
                )

        elif event_type == "subkani_task_start":
            task = event_data.get("task")
            if task:
                self.subkani_status[task] = "running"
                self.subkani_calls.setdefault(task, [])
                self.thinking_dirty = True
                await self.maybe_flush_thinking()

        elif event_type == "subkani_tool_call_start":
            task = event_data.get("task")
            call_id = event_data.get("id")
            if task and call_id:
                call = {
                    "id": call_id,
                    "name": event_data.get("name"),
                    "arguments": event_data.get("arguments"),
                }
                self.subkani_calls.setdefault(task, []).append(call)
                self.subkani_calls_by_id[call_id] = (task, call)
                self.thinking_dirty = True
                await self.maybe_flush_thinking()

        elif event_type == "subkani_tool_call_end":
            call_id = event_data.get("id")
            if call_id and call_id in self.subkani_calls_by_id:
                _, call = self.subkani_calls_by_id[call_id]
                call["result"] = event_data.get("result")
                self.thinking_dirty = True
                await self.maybe_flush_thinking()

        elif event_type == "subkani_task_end":
            task = event_data.get("task")
            if task:
                self.subkani_status[task] = event_data.get("status") or "done"
                self.thinking_dirty = True
                await self.maybe_flush_thinking()

        elif event_type == "tool_call_start":
            call_id = event_data.get("id")
            if call_id:
                self.tool_calls_by_id[call_id] = {
                    "id": call_id,
                    "name": event_data.get("name"),
                    "arguments": event_data.get("arguments"),
                }
                self.thinking_dirty = True
                await self.maybe_flush_thinking()

        elif event_type == "tool_call_end":
            call_id = event_data.get("id")
            if call_id and call_id in self.tool_calls_by_id:
                self.tool_calls_by_id[call_id]["result"] = event_data.get("result")
                self.tool_calls.append(self.tool_calls_by_id[call_id])
                self.thinking_dirty = True
                await self.maybe_flush_thinking()

        elif event_type == STRATEGY_LINK:
            graph_id = self.resolve_graph_id(event_data.get("graphId"))
            if graph_id:
                event_data["graphId"] = graph_id
                self.pending_strategy_link[str(graph_id)] = event_data

            graph_uuid = parse_uuid(event_data.get("graphId"))
            if graph_uuid:
                wdk_strategy_id = event_data.get("wdkStrategyId")
                if wdk_strategy_id:
                    updated = await self.strategy_repo.update(
                        strategy_id=graph_uuid,
                        wdk_strategy_id=wdk_strategy_id,
                    )
                    if not updated:
                        await self.strategy_repo.create(
                            user_id=self.user_id,
                            name=event_data.get("name") or "Draft Strategy",
                            site_id=self.site_id,
                            record_type=None,
                            plan={},
                            wdk_strategy_id=wdk_strategy_id,
                            strategy_id=graph_uuid,
                        )
                event_data = {**event_data, "strategySnapshotId": str(graph_uuid)}

        return sse_event(event_type, event_data)

    async def finalize(self) -> list[str]:
        """Finalize the stream: persist messages + snapshots, and return extra SSE lines."""
        extra_events: list[str] = []

        await self.maybe_flush_thinking(force=True)
        await self.strategy_repo.clear_thinking(self.strategy.id)

        normalized_tool_calls = normalize_tool_calls(self.tool_calls)
        normalized_subkani = normalize_subkani_activity(
            self.subkani_calls, self.subkani_status
        )

        if not self.assistant_messages and (normalized_tool_calls or normalized_subkani):
            self.assistant_messages = ["Done."]

        for index, content in enumerate(self.assistant_messages):
            tool_calls_payload = (
                normalized_tool_calls
                if normalized_tool_calls and index == len(self.assistant_messages) - 1
                else None
            )
            subkani_payload = (
                normalized_subkani
                if normalized_subkani and index == len(self.assistant_messages) - 1
                else None
            )
            assistant_message = {
                "role": "assistant",
                "content": content,
                "toolCalls": tool_calls_payload,
                "subKaniActivity": subkani_payload,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            await self.strategy_repo.add_message(self.strategy.id, assistant_message)

        if self.latest_plans:
            for graph_id, payload in self.latest_plans.items():
                graph_uuid = self.strategy.id
                latest_plan = payload.get("plan")
                latest_name = payload.get("name") or "Draft Strategy"
                latest_record_type = payload.get("recordType")
                latest_description = payload.get("description")
                snapshot = self.latest_graph_snapshots.get(graph_id)
                if not latest_plan:
                    continue

                if latest_description is not None and isinstance(latest_plan, dict):
                    metadata = latest_plan.get("metadata")
                    if not isinstance(metadata, dict):
                        metadata = {}
                    metadata["description"] = latest_description
                    latest_plan["metadata"] = metadata

                try:
                    if isinstance(snapshot, dict) and snapshot.get("steps"):
                        # Snapshot-only persistence is deprecated; prefer plan persistence.
                        steps_data = build_steps_data_from_graph_snapshot(snapshot)
                    else:
                        steps_data = (
                            build_steps_data_from_plan(latest_plan)
                            if isinstance(latest_plan, dict)
                            else []
                        )

                    if isinstance(snapshot, dict):
                        latest_name = snapshot.get("name") or snapshot.get("graphName") or latest_name
                        latest_record_type = snapshot.get("recordType") or latest_record_type
                        latest_description = snapshot.get("description") or latest_description
                        root_step_id = snapshot.get("rootStepId") or None
                    else:
                        root_step_id = None

                    strategy_ast = from_dict(latest_plan)
                    canonical_plan = strategy_ast.to_dict()

                    updated = await self.strategy_repo.update(
                        strategy_id=graph_uuid,
                        name=latest_name,
                        title=latest_name,
                        plan=canonical_plan,
                        record_type=latest_record_type,
                    )
                    if not updated:
                        await self.strategy_repo.create(
                            user_id=self.user_id,
                            name=latest_name,
                            title=latest_name,
                            site_id=self.site_id,
                            record_type=latest_record_type,
                            plan=canonical_plan,
                            strategy_id=graph_uuid,
                        )
                    if graph_uuid == self.strategy.id:
                        await self.strategy_repo.update(
                            strategy_id=self.strategy.id,
                            title=latest_name,
                        )

                    pending = self.pending_strategy_link.get(graph_id)
                    if pending:
                        wdk_strategy_id = pending.get("wdkStrategyId")
                        if wdk_strategy_id:
                            await self.strategy_repo.update(
                                strategy_id=graph_uuid,
                                wdk_strategy_id=wdk_strategy_id,
                            )
                        pending = {**pending, "strategySnapshotId": str(graph_uuid)}
                        extra_events.append(sse_event("strategy_link", pending))
                except Exception as e:
                    logger.warning(
                        "Failed to save strategy snapshot",
                        error=str(e),
                        graph_id=graph_id,
                    )

        if self.latest_graph_snapshots:
            for graph_id, snapshot in self.latest_graph_snapshots.items():
                if graph_id in self.latest_plans or not isinstance(snapshot, dict):
                    continue
                graph_uuid = self.strategy.id
                steps_data = build_steps_data_from_graph_snapshot(snapshot)
                if not steps_data:
                    continue
                root_step_id = snapshot.get("rootStepId") or None
                record_type = snapshot.get("recordType")
                name = snapshot.get("graphName") or snapshot.get("name")
                updated = await self.strategy_repo.update(
                    strategy_id=graph_uuid,
                    name=name,
                    title=name,
                    record_type=record_type,
                )
                if not updated:
                    await self.strategy_repo.create(
                        user_id=self.user_id,
                        name=name or "Draft Strategy",
                        title=name or "Draft Strategy",
                        site_id=self.site_id,
                        record_type=record_type,
                        plan={},
                        strategy_id=graph_uuid,
                    )
                if graph_uuid == self.strategy.id:
                    await self.strategy_repo.update(
                        strategy_id=self.strategy.id,
                        title=name or "Draft Strategy",
                    )

        return extra_events

    async def handle_exception(self, e: Exception) -> str:
        logger.error("Chat error", error=str(e))
        await self.strategy_repo.clear_thinking(self.strategy.id)
        return sse_error(str(e))

