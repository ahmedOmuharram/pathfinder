"""Chat stream event processing + persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from veupath_chatbot.domain.strategy.ast import from_dict
from veupath_chatbot.persistence.models import Strategy
from veupath_chatbot.persistence.repo import StrategyRepository
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import (
    JSONArray,
    JSONObject,
    JSONValue,
    as_json_object,
)
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
    STRATEGY_META,
)
from .sse import sse_error, sse_event, sse_message_start
from .thinking import (
    build_thinking_payload,
    normalize_subkani_activity,
    normalize_tool_calls,
)
from .utils import parse_uuid, sanitize_markdown

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
        strategy_payload: JSONObject,
        mode: str = "execute",
    ) -> None:
        self.strategy_repo = strategy_repo
        self.site_id = site_id
        self.user_id = user_id
        self.strategy = strategy
        self.auth_token = auth_token
        self.strategy_payload = strategy_payload
        self.mode = mode

        self.assistant_messages: list[str] = []
        self.citations: JSONArray = []
        self.planning_artifacts: JSONArray = []
        self.tool_calls: JSONArray = []
        self.tool_calls_by_id: dict[str, JSONObject] = {}
        self.subkani_calls: dict[str, JSONArray] = {}
        self.subkani_calls_by_id: dict[str, tuple[str, JSONObject]] = {}
        self.subkani_status: dict[str, str] = {}
        self.latest_plans: dict[str, JSONObject] = {}
        self.latest_graph_snapshots: dict[str, JSONObject] = {}
        self.pending_strategy_link: dict[str, JSONObject] = {}

        self.last_thinking_flush = datetime.now(UTC)
        self.thinking_dirty = False
        self.thinking_flush_interval = 2.0

    def resolve_graph_id(self, raw_id: str | None | JSONValue) -> str | None:
        """Resolve graph ID, converting JSONValue to str if needed."""
        if raw_id is None:
            return None
        if isinstance(raw_id, str):
            return raw_id
        return str(raw_id)

    async def maybe_flush_thinking(self, *, force: bool = False) -> None:
        if not self.thinking_dirty:
            return
        now = datetime.now(UTC)
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
            auth_token=self.auth_token,
            strategy_id=str(self.strategy.id),
            strategy=self.strategy_payload,
        )

    async def on_event(self, event_type: str, event_data: JSONObject) -> str | None:
        """Process one semantic event; returns SSE line (or None if skipped)."""
        if event_type == "message_start":
            return None

        if event_type == "assistant_message":
            content_value = event_data.get("content", "") or ""
            content = str(content_value) if content_value is not None else ""
            content = sanitize_markdown(content)
            event_data["content"] = content
            if content:
                self.assistant_messages.append(content)

        elif event_type == "citations":
            citations = event_data.get("citations")
            if isinstance(citations, list):
                for c in citations:
                    if isinstance(c, dict):
                        self.citations.append(c)

        elif event_type == "planning_artifact":
            artifact = event_data.get("planningArtifact")
            if isinstance(artifact, dict):
                self.planning_artifacts.append(artifact)

        elif event_type == GRAPH_SNAPSHOT:
            snapshot_value = event_data.get("graphSnapshot")
            if isinstance(snapshot_value, dict):
                snapshot = as_json_object(snapshot_value)
                graph_id_value = snapshot.get("graphId")
                graph_id = self.resolve_graph_id(graph_id_value)
                if graph_id:
                    snapshot["graphId"] = graph_id
                    event_data["graphSnapshot"] = snapshot
                    self.latest_graph_snapshots[str(graph_id)] = snapshot
                    # Persist immediately so model-added steps are never "unsaved".
                    graph_uuid = parse_uuid(graph_id)
                    if graph_uuid:
                        steps_data = build_steps_data_from_graph_snapshot(snapshot)
                        root_step_id_value = snapshot.get("rootStepId")
                        root_step_id = (
                            str(root_step_id_value)
                            if isinstance(root_step_id_value, str)
                            else None
                        )
                        name_value = snapshot.get("name")
                        graph_name_value = snapshot.get("graphName")
                        name: str | None = None
                        if isinstance(name_value, str):
                            name = name_value
                        elif isinstance(graph_name_value, str):
                            name = graph_name_value
                        record_type_value = snapshot.get("recordType")
                        record_type = (
                            str(record_type_value)
                            if isinstance(record_type_value, str)
                            else None
                        )
                        updated = await self.strategy_repo.update(
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
                            await self.strategy_repo.create(
                                user_id=self.user_id,
                                name=name_str,
                                title=name_str,
                                site_id=self.site_id,
                                record_type=record_type,
                                plan={},
                                steps=steps_data,
                                root_step_id=root_step_id,
                                strategy_id=graph_uuid,
                            )

        elif event_type == GRAPH_PLAN:
            graph_id_value = event_data.get("graphId")
            graph_id = self.resolve_graph_id(graph_id_value)
            if graph_id:
                plan_value = event_data.get("plan")
                name_value = event_data.get("name")
                record_type_value = event_data.get("recordType")
                description_value = event_data.get("description")
                self.latest_plans[str(graph_id)] = {
                    "plan": plan_value,
                    "name": name_value,
                    "recordType": record_type_value,
                    "description": description_value,
                }

        elif event_type == STRATEGY_META:
            graph_id_value = event_data.get("graphId")
            graph_id = self.resolve_graph_id(graph_id_value)
            graph_uuid = parse_uuid(graph_id) if graph_id else None
            if graph_uuid:
                meta_name_value = event_data.get("name")
                meta_graph_name_value = event_data.get("graphName")
                meta_name: str | None = None
                if isinstance(meta_name_value, str):
                    meta_name = meta_name_value
                elif isinstance(meta_graph_name_value, str):
                    meta_name = meta_graph_name_value
                record_type_value = event_data.get("recordType")
                record_type = (
                    str(record_type_value)
                    if isinstance(record_type_value, str)
                    else None
                )
                await self.strategy_repo.update(
                    strategy_id=graph_uuid,
                    name=meta_name,
                    title=meta_name,
                    record_type=record_type,
                )

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
            task_value = event_data.get("task")
            task = str(task_value) if isinstance(task_value, str) else None
            if task:
                self.subkani_status[task] = "running"
                self.subkani_calls.setdefault(task, [])
                self.thinking_dirty = True
                await self.maybe_flush_thinking()

        elif event_type == "subkani_tool_call_start":
            task_value = event_data.get("task")
            call_id_value = event_data.get("id")
            task = str(task_value) if isinstance(task_value, str) else None
            call_id = str(call_id_value) if isinstance(call_id_value, str) else None
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
            call_id_value = event_data.get("id")
            call_id = str(call_id_value) if isinstance(call_id_value, str) else None
            if call_id and call_id in self.subkani_calls_by_id:
                _, call = self.subkani_calls_by_id[call_id]
                call["result"] = event_data.get("result")
                self.thinking_dirty = True
                await self.maybe_flush_thinking()

        elif event_type == "subkani_task_end":
            task_value = event_data.get("task")
            task = str(task_value) if isinstance(task_value, str) else None
            if task:
                status_value = event_data.get("status")
                status = str(status_value) if isinstance(status_value, str) else "done"
                self.subkani_status[task] = status
                self.thinking_dirty = True
                await self.maybe_flush_thinking()

        elif event_type == "tool_call_start":
            call_id_value = event_data.get("id")
            call_id = str(call_id_value) if isinstance(call_id_value, str) else None
            if call_id:
                self.tool_calls_by_id[call_id] = {
                    "id": call_id,
                    "name": event_data.get("name"),
                    "arguments": event_data.get("arguments"),
                }
                self.thinking_dirty = True
                await self.maybe_flush_thinking()

        elif event_type == "tool_call_end":
            call_id_value = event_data.get("id")
            call_id = str(call_id_value) if isinstance(call_id_value, str) else None
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

            graph_id_for_uuid_value = event_data.get("graphId")
            graph_id_for_uuid = (
                str(graph_id_for_uuid_value)
                if isinstance(graph_id_for_uuid_value, str)
                else None
            )
            graph_uuid = parse_uuid(graph_id_for_uuid)
            if graph_uuid:
                wdk_strategy_id_value = event_data.get("wdkStrategyId")
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
                    updated = await self.strategy_repo.update(
                        strategy_id=graph_uuid,
                        wdk_strategy_id=wdk_strategy_id,
                    )
                    if not updated:
                        name_value = event_data.get("name")
                        name = (
                            str(name_value)
                            if isinstance(name_value, str)
                            else "Draft Strategy"
                        )
                        await self.strategy_repo.create(
                            user_id=self.user_id,
                            name=name,
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

        if not self.assistant_messages and (
            normalized_tool_calls or normalized_subkani
        ):
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
            assistant_message: JSONObject = {
                "role": "assistant",
                "content": content,
                "toolCalls": tool_calls_payload,
                "subKaniActivity": subkani_payload,
                "mode": self.mode,
                "timestamp": datetime.now(UTC).isoformat(),
            }
            if index == len(self.assistant_messages) - 1:
                if self.citations:
                    assistant_message["citations"] = self.citations
                if self.planning_artifacts:
                    assistant_message["planningArtifacts"] = self.planning_artifacts
            await self.strategy_repo.add_message(self.strategy.id, assistant_message)

        if self.latest_plans:
            for graph_id, payload in self.latest_plans.items():
                graph_uuid = self.strategy.id
                latest_plan = payload.get("plan")
                name_value = payload.get("name")
                latest_name = (
                    str(name_value) if isinstance(name_value, str) else "Draft Strategy"
                )
                record_type_value = payload.get("recordType")
                latest_record_type = (
                    str(record_type_value)
                    if isinstance(record_type_value, str)
                    else None
                )
                description_value = payload.get("description")
                latest_description = (
                    str(description_value)
                    if isinstance(description_value, str)
                    else None
                )
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
                    else:
                        updated = await self.strategy_repo.update(
                            strategy_id=graph_uuid,
                            name=latest_name,
                            title=latest_name,
                            record_type=latest_record_type,
                            steps=steps_data,
                            root_step_id=root_step_id,
                            root_step_id_set=True,
                        )
                        if not updated:
                            await self.strategy_repo.create(
                                user_id=self.user_id,
                                name=latest_name,
                                title=latest_name,
                                site_id=self.site_id,
                                record_type=latest_record_type,
                                plan={},
                                steps=steps_data,
                                root_step_id=root_step_id,
                                strategy_id=graph_uuid,
                            )
                    if graph_uuid == self.strategy.id:
                        await self.strategy_repo.update(
                            strategy_id=self.strategy.id,
                            title=latest_name,
                        )

                    pending = self.pending_strategy_link.get(graph_id)
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
                root_step_id_value = snapshot.get("rootStepId")
                root_step_id = (
                    str(root_step_id_value)
                    if isinstance(root_step_id_value, str)
                    else None
                )
                record_type_value = snapshot.get("recordType")
                record_type = (
                    str(record_type_value)
                    if isinstance(record_type_value, str)
                    else None
                )
                graph_name_value = snapshot.get("graphName")
                name_value = snapshot.get("name")
                name = (
                    str(graph_name_value)
                    if isinstance(graph_name_value, str)
                    else (str(name_value) if isinstance(name_value, str) else None)
                )
                updated = await self.strategy_repo.update(
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
                    await self.strategy_repo.create(
                        user_id=self.user_id,
                        name=name_str,
                        title=name_str,
                        site_id=self.site_id,
                        record_type=record_type,
                        plan={},
                        steps=steps_data,
                        root_step_id=root_step_id,
                        strategy_id=graph_uuid,
                    )
                if graph_uuid == self.strategy.id:
                    name_str = name or "Draft Strategy"
                    await self.strategy_repo.update(
                        strategy_id=self.strategy.id,
                        title=name_str,
                    )

        return extra_events

    async def handle_exception(self, e: Exception) -> str:
        logger.error("Chat error", error=str(e))
        await self.strategy_repo.clear_thinking(self.strategy.id)
        return sse_error(str(e))
