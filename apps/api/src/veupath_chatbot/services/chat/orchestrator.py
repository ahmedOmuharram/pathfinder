"""Chat orchestration entrypoint (service layer).

Implementation details are split across smaller modules. The HTTP layer should
call `start_chat_stream` and remain thin.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

from veupath_chatbot.ai.agents.factory import create_agent, resolve_effective_model_id
from veupath_chatbot.ai.models.catalog import ModelProvider, ReasoningEffort
from veupath_chatbot.persistence.repo import (
    StrategyRepository,
    UserRepository,
)
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.chat.bootstrap import (
    append_user_message,
    build_chat_history,
    build_strategy_payload,
    ensure_strategy,
)
from veupath_chatbot.services.chat.processor import ChatStreamProcessor
from veupath_chatbot.services.chat.utils import parse_selected_nodes
from veupath_chatbot.transport.http.streaming import stream_chat

logger = get_logger(__name__)


def _use_mock_chat_provider() -> bool:
    from veupath_chatbot.platform.config import get_settings

    return get_settings().chat_provider.strip().lower() == "mock"


async def _mock_stream_chat(
    *, message: str, strategy_id: str | None = None
) -> AsyncIterator[JSONObject]:
    """Deterministic, offline-friendly stream for tests/E2E runs.

    Matches the semantic event contract produced by `stream_chat()`.
    """
    deltas = [
        "[mock] ",
        "I received your message: ",
        message,
    ]
    message_id = str(uuid4())
    for d in deltas:
        if "slow" in message.lower():
            await asyncio.sleep(0.2)
        yield {"type": "assistant_delta", "data": {"messageId": message_id, "delta": d}}

    msg_lower = message.lower()
    if "artifact graph" in msg_lower:
        now = datetime.now(UTC).isoformat()
        yield {
            "type": "planning_artifact",
            "data": {
                "planningArtifact": {
                    "id": "mock_exec_graph_artifact",
                    "title": "Mock graph artifact",
                    "summaryMarkdown": "A deterministic multi-step artifact for E2E graph interaction tests.",
                    "assumptions": [],
                    "parameters": {},
                    "proposedStrategyPlan": {
                        "recordType": "gene",
                        "root": {
                            "id": "mock_transform_1",
                            "searchName": "mock_transform",
                            "displayName": "Mock transform step",
                            "parameters": {},
                            "primaryInput": {
                                "id": "mock_search_1",
                                "searchName": "mock_search",
                                "displayName": "Mock search step",
                                "parameters": {},
                            },
                        },
                        "metadata": {"name": "Mock graph plan"},
                    },
                    "createdAt": now,
                }
            },
        }
    elif "delegate_strategy_subtasks" in msg_lower or "delegation" in msg_lower:
        yield {
            "type": "subkani_task_start",
            "data": {"task": "delegate:build-strategy"},
        }
        yield {
            "type": "subkani_tool_call_start",
            "data": {
                "task": "delegate:build-strategy",
                "id": "tc_delegate_1",
                "name": "search_for_searches",
                "arguments": '{"query":"ortholog transform","record_type":"gene","limit":3}',
            },
        }
        yield {
            "type": "subkani_tool_call_end",
            "data": {
                "task": "delegate:build-strategy",
                "id": "tc_delegate_1",
                "result": '{"rag":{"data":[],"note":""},"wdk":{"data":[],"note":"mock"}}',
            },
        }
        yield {
            "type": "subkani_task_end",
            "data": {"task": "delegate:build-strategy", "status": "done"},
        }

        gid = strategy_id or "mock_graph_delegation"
        yield {
            "type": "strategy_update",
            "data": {
                "graphId": gid,
                "step": {
                    "graphId": gid,
                    "stepId": "mock_search_1",
                    "kind": "search",
                    "displayName": "Delegated search step",
                    "searchName": "mock_search",
                    "parameters": {"q": "gametocyte", "min": 10},
                    "recordType": "gene",
                    "graphName": "Delegation-built strategy",
                    "description": "A deterministic delegated strategy for E2E.",
                },
            },
        }
        yield {
            "type": "strategy_update",
            "data": {
                "graphId": gid,
                "step": {
                    "graphId": gid,
                    "stepId": "mock_transform_1",
                    "kind": "transform",
                    "displayName": "Delegated transform step",
                    "searchName": "mock_transform",
                    "primaryInputStepId": "mock_search_1",
                    "parameters": {"insertBetween": True, "species": "P. falciparum"},
                    "recordType": "gene",
                },
            },
        }
        yield {
            "type": "strategy_update",
            "data": {
                "graphId": gid,
                "step": {
                    "graphId": gid,
                    "stepId": "mock_combine_1",
                    "kind": "combine",
                    "displayName": "Delegated combine step",
                    "operator": "UNION",
                    "primaryInputStepId": "mock_transform_1",
                    "secondaryInputStepId": "mock_search_1",
                    "parameters": {},
                    "recordType": "gene",
                },
            },
        }

        yield {
            "type": "assistant_message",
            "data": {
                "messageId": message_id,
                "content": "[mock] Delegation complete. Built a multi-step strategy and emitted sub-kani activity.",
            },
        }
        yield {"type": "message_end", "data": {}}
        return

    yield {
        "type": "assistant_message",
        "data": {"messageId": message_id, "content": "".join(deltas)},
    }

    yield {"type": "message_end", "data": {}}


async def start_chat_stream(
    *,
    message: str,
    site_id: str,
    strategy_id: UUID | None,
    user_id: UUID,
    user_repo: UserRepository,
    strategy_repo: StrategyRepository,
    # Per-request model overrides
    provider_override: ModelProvider | None = None,
    model_override: str | None = None,
    reasoning_effort: ReasoningEffort | None = None,
    mentions: list[dict[str, str]] | None = None,
) -> AsyncIterator[str]:
    """Start an SSE stream for a chat turn.

    Every conversation is strategy-backed. The unified agent decides
    per-turn whether to research/plan or build/execute — there is no
    separate "plan mode" on the API surface.

    Returns an ``sse_iterator`` that yields SSE-formatted strings.
    Authentication is handled at login time; no token is created here.
    """
    await user_repo.get_or_create(user_id)

    # Build rich context from @-mentions (strategies and experiments).
    mentioned_context: str | None = None
    if mentions:
        from veupath_chatbot.services.chat.mention_context import build_mention_context

        mentioned_context = await build_mention_context(mentions, strategy_repo) or None

    # All conversations are strategy-bound — the unified agent decides the approach.
    strategy = await ensure_strategy(
        strategy_repo,
        user_id=user_id,
        site_id=site_id,
        strategy_id=strategy_id,
    )

    await append_user_message(strategy_repo, strategy_id=strategy.id, message=message)
    selected_nodes, model_message = parse_selected_nodes(message)

    history = await build_chat_history(strategy_repo, strategy=strategy)
    strategy_payload = build_strategy_payload(strategy)

    # Provide both canonical plan and snapshot-derived steps so the agent can rehydrate
    # even when plan persistence failed (steps/rootStepId fallback).
    strategy_graph_payload: JSONObject = {
        "id": str(strategy.id),
        "name": strategy.name,
        "plan": strategy.plan,
        "steps": strategy.steps,
        "rootStepId": str(strategy.root_step_id) if strategy.root_step_id else None,
        "recordType": strategy.record_type,
    }

    # Resolve the effective model: per-request > persisted > server default.
    effective_model = resolve_effective_model_id(
        model_override=model_override,
        persisted_model_id=strategy.model_id,
    )

    agent = create_agent(
        site_id=site_id,
        user_id=user_id,
        chat_history=history,
        strategy_graph=strategy_graph_payload,
        selected_nodes=selected_nodes,
        provider_override=provider_override,
        model_override=effective_model,
        reasoning_effort=reasoning_effort,
        mentioned_context=mentioned_context,
    )

    # Persist model selection on the conversation.
    if effective_model != strategy.model_id:
        await strategy_repo.update(
            strategy.id, model_id=effective_model, model_id_set=True
        )

    async def event_generator() -> AsyncIterator[str]:
        processor = ChatStreamProcessor(
            strategy_repo=strategy_repo,
            site_id=site_id,
            user_id=user_id,
            strategy=strategy,
            strategy_payload=strategy_payload,
        )
        try:
            yield processor.start_event()

            stream_iter = (
                _mock_stream_chat(
                    message=model_message,
                    strategy_id=str(strategy.id),
                )
                if _use_mock_chat_provider()
                else stream_chat(agent, model_message)
            )
            async for event_value in stream_iter:
                if not isinstance(event_value, dict):
                    continue
                event = event_value
                event_type_raw = event.get("type", "")
                event_type = event_type_raw if isinstance(event_type_raw, str) else ""
                event_data_raw = event.get("data")
                event_data = event_data_raw if isinstance(event_data_raw, dict) else {}
                sse_line = await processor.on_event(event_type, event_data)
                if sse_line:
                    yield sse_line

            for extra in await processor.finalize():
                yield extra
        except Exception as e:
            yield await processor.handle_exception(e)

    return event_generator()
