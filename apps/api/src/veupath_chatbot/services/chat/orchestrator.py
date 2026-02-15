"""Chat orchestration entrypoint (service layer).

Implementation details are split across smaller modules. The HTTP layer should
call `start_chat_stream` and remain thin.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

from kani import ChatMessage, ChatRole

from veupath_chatbot.ai.agent_factory import (
    ChatMode,
    create_agent,
    resolve_effective_model_id,
)
from veupath_chatbot.ai.model_catalog import ModelProvider, ReasoningEffort
from veupath_chatbot.persistence.repo import (
    PlanSessionRepository,
    StrategyRepository,
    UserRepository,
)
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONArray, JSONObject
from veupath_chatbot.services.chat.bootstrap import (
    append_user_message,
    build_chat_history,
    build_strategy_payload,
    ensure_strategy,
    ensure_user,
)
from veupath_chatbot.services.chat.plan_processor import PlanStreamProcessor
from veupath_chatbot.services.chat.processor import ChatStreamProcessor
from veupath_chatbot.services.chat.utils import parse_selected_nodes
from veupath_chatbot.transport.http.streaming import stream_chat

logger = get_logger(__name__)


def _use_mock_chat_provider() -> bool:
    return (os.environ.get("PATHFINDER_CHAT_PROVIDER") or "").strip().lower() == "mock"


async def _mock_stream_chat(
    *, mode: str, message: str, strategy_id: str | None = None
) -> AsyncIterator[JSONObject]:
    """
    Deterministic, offline-friendly stream that matches the semantic event contract
    produced by `stream_chat()`.

    This is intended for tests/E2E runs; it should never require external services.
    """
    deltas = [
        f"[mock:{mode}] ",
        "I received your message: ",
        message,
    ]
    message_id = str(uuid4())
    for d in deltas:
        if "slow" in message.lower():
            await asyncio.sleep(0.2)
        yield {"type": "assistant_delta", "data": {"messageId": message_id, "delta": d}}

    # Optionally emit deterministic strategy-planning artifacts in executor mode so
    # the UI can exercise graph + selection flows in E2E.
    msg_lower = message.lower()
    if mode == "execute" and "artifact graph" in msg_lower:
        now = datetime.now(UTC).isoformat()
        yield {
            "type": "planning_artifact",
            "data": {
                "planningArtifact": {
                    "id": "mock_exec_graph_artifact",
                    "title": "Mock executor graph artifact",
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
    # Executor-mode: deterministic delegation/sub-kani + graph build flow.
    elif mode == "execute" and (
        "delegate_strategy_subtasks" in msg_lower or "delegation" in msg_lower
    ):
        # Emit a sub-kani task with a tool call so the UI can render Sub-kani Activity.
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

        # Emit a few strategy_update events to build a multi-step graph deterministically.
        # Use the real strategy_id so the frontend doesn't filter them out.
        gid = strategy_id or "mock_graph_delegation"
        yield {
            "type": "strategy_update",
            "data": {
                "graphId": gid,
                "step": {
                    "graphId": gid,
                    "stepId": "mock_search_1",
                    "type": "search",
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
                    "type": "transform",
                    "displayName": "Delegated transform step",
                    "searchName": "mock_transform",
                    "inputStepId": "mock_search_1",
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
                    "type": "combine",
                    "displayName": "Delegated combine step",
                    "operator": "UNION",
                    "leftStepId": "mock_transform_1",
                    "rightStepId": "mock_search_1",
                    "parameters": {},
                    "recordType": "gene",
                },
            },
        }

        # Ensure the assistant message still arrives for the UI transcript.
        yield {
            "type": "assistant_message",
            "data": {
                "messageId": message_id,
                "content": "[mock:execute] Delegation complete. Built a multi-step strategy and emitted sub-kani activity.",
            },
        }
        yield {"type": "message_end", "data": {}}
        return

    # Back-compat: single-step artifact used by existing E2E tests.
    elif mode == "execute" and "artifact" in msg_lower:
        now = datetime.now(UTC).isoformat()
        yield {
            "type": "planning_artifact",
            "data": {
                "planningArtifact": {
                    "id": "mock_exec_artifact",
                    "title": "Mock executor artifact",
                    "summaryMarkdown": "A deterministic artifact for E2E validation.",
                    "assumptions": [],
                    "parameters": {},
                    "proposedStrategyPlan": {
                        "recordType": "gene",
                        "root": {
                            "id": "mock_step_1",
                            "searchName": "mock_search",
                            "displayName": "Mock search step",
                            "parameters": {},
                        },
                        "metadata": {"name": "Mock plan"},
                    },
                    "createdAt": now,
                }
            },
        }

    yield {
        "type": "assistant_message",
        "data": {"messageId": message_id, "content": "".join(deltas)},
    }

    if mode == "plan":
        # Emit one minimal planning artifact so UI can exercise Plan→Execute flows.
        yield {
            "type": "planning_artifact",
            "data": {
                "planningArtifact": {
                    "id": "mock_artifact",
                    "title": "Mock planning artifact",
                    "summaryMarkdown": "This is a deterministic artifact emitted by the mock provider.",
                    "assumptions": [],
                    "parameters": {},
                    "createdAt": datetime.now(UTC).isoformat(),
                }
            },
        }
        # Emit a deterministic delegation draft for E2E plan→delegation→execute flows.
        if "delegation" in msg_lower:
            yield {
                "type": "planning_artifact",
                "data": {
                    "planningArtifact": {
                        "id": "delegation_draft",
                        "title": "Delegation plan (draft)",
                        "summaryMarkdown": "A deterministic delegation draft for E2E.",
                        "assumptions": [],
                        "parameters": {
                            "delegationGoal": "Build a gene strategy using an ortholog transform and a combine.",
                            "delegationPlan": {
                                "type": "task",
                                "task": "build_strategy",
                                "context": {"recordType": "gene"},
                                "steps": [
                                    {
                                        "type": "task",
                                        "task": "find_search",
                                        "context": {"query": "gametocyte RNA-seq"},
                                    },
                                    {
                                        "type": "task",
                                        "task": "insert_transform",
                                        "context": {"tool": "ortholog"},
                                    },
                                ],
                            },
                        },
                        "createdAt": datetime.now(UTC).isoformat(),
                    }
                },
            }
        if "executor" in message.lower() or "build" in message.lower():
            yield {
                "type": "executor_build_request",
                "data": {
                    "executorBuildRequest": {
                        "message": "Build a minimal strategy for the user's goal.",
                    }
                },
            }

    yield {"type": "message_end", "data": {}}


async def start_chat_stream(
    *,
    message: str,
    site_id: str,
    strategy_id: UUID | None,
    plan_session_id: UUID | None,
    mode: str = "execute",
    user_id: UUID,
    user_repo: UserRepository,
    strategy_repo: StrategyRepository,
    plan_repo: PlanSessionRepository,
    # Per-request model overrides
    provider_override: ModelProvider | None = None,
    model_override: str | None = None,
    reasoning_effort: ReasoningEffort | None = None,
    reference_strategy_id: UUID | None = None,
) -> AsyncIterator[str]:
    """Start an SSE stream for a chat turn.

    Returns an ``sse_iterator`` that yields SSE-formatted strings.
    Authentication is handled at login time; no token is created here.
    """
    user_id = await ensure_user(user_repo, user_id)

    if mode == "plan":
        # Plan sessions are not strategies; do not create/modify the strategy sidebar.
        # If a plan session id is not provided, create a new one.
        plan_session = (
            await plan_repo.get_by_id(plan_session_id) if plan_session_id else None
        )
        if plan_session is None:
            plan_session = await plan_repo.create(
                user_id=user_id, site_id=site_id, title="New Conversation"
            )

        user_message: JSONObject = {
            "role": "user",
            "content": message,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        await plan_repo.add_message(plan_session.id, user_message)
        await plan_repo.clear_thinking(plan_session.id)

        # For planning mode we do not support node-selection encoding (graph-less), but we
        # still strip it if present so the model sees clean text.
        _, model_message = parse_selected_nodes(message)

        await plan_repo.refresh(plan_session)
        history: list[ChatMessage] = []
        for msg_value in plan_session.messages or []:
            if not isinstance(msg_value, dict):
                continue
            msg = msg_value
            role_raw = msg.get("role")
            content_raw = msg.get("content")
            if not content_raw or not isinstance(content_raw, str):
                continue
            content = content_raw
            if role_raw == "user":
                _, cleaned = parse_selected_nodes(content)
                history.append(ChatMessage(role=ChatRole.USER, content=cleaned))
            elif role_raw == "assistant":
                history.append(ChatMessage(role=ChatRole.ASSISTANT, content=content))

        async def _get_plan_artifacts() -> JSONArray:
            ps = await plan_repo.get_by_id(plan_session.id)
            artifacts = (ps.planning_artifacts or []) if ps else []
            return artifacts

        # Provide the latest saved delegation draft (if any) directly in the planner's
        # system prompt so the model doesn't need to "remember" via extra tool calls.
        delegation_draft_artifact: JSONObject | None = None
        for a in plan_session.planning_artifacts or []:
            if isinstance(a, dict) and a.get("id") == "delegation_draft":
                delegation_draft_artifact = a
                break

        # If a reference strategy was provided, load its graph for context.
        ref_strategy_graph: JSONObject | None = None
        if reference_strategy_id:
            ref_strategy = await strategy_repo.get_by_id(reference_strategy_id)
            if ref_strategy:
                ref_strategy_graph = {
                    "id": str(ref_strategy.id),
                    "name": ref_strategy.name,
                    "plan": ref_strategy.plan,
                    "steps": ref_strategy.steps,
                    "rootStepId": (
                        str(ref_strategy.root_step_id)
                        if ref_strategy.root_step_id
                        else None
                    ),
                    "recordType": ref_strategy.record_type,
                }

        # Resolve the effective model: per-request > persisted > server default.
        effective_model = resolve_effective_model_id(
            model_override=model_override,
            persisted_model_id=plan_session.model_id,
        )

        agent = create_agent(
            site_id=site_id,
            user_id=user_id,
            chat_history=history,
            strategy_graph=ref_strategy_graph,
            selected_nodes=None,
            delegation_draft_artifact=delegation_draft_artifact,
            plan_session_id=plan_session.id,
            get_plan_session_artifacts=_get_plan_artifacts,
            mode="plan",
            provider_override=provider_override,
            model_override=effective_model,
            reasoning_effort=reasoning_effort,
        )

        # Persist model selection on the conversation.
        if effective_model != plan_session.model_id:
            await plan_repo.update_model_id(plan_session.id, effective_model)

        plan_payload: JSONObject = {
            "id": str(plan_session.id),
            "siteId": plan_session.site_id,
            "title": plan_session.title,
        }

        async def plan_event_generator() -> AsyncIterator[str]:
            processor = PlanStreamProcessor(
                plan_repo=plan_repo,
                user_id=user_id,
                plan_session=plan_session,
                plan_payload=plan_payload,
                mode=mode,
            )
            try:
                yield processor.start_event()
                stream_iter = (
                    _mock_stream_chat(mode=mode, message=model_message)
                    if _use_mock_chat_provider()
                    else stream_chat(agent, model_message)
                )
                async for event_value in stream_iter:
                    if not isinstance(event_value, dict):
                        continue
                    event = event_value
                    event_type_raw = event.get("type", "")
                    event_type = (
                        event_type_raw if isinstance(event_type_raw, str) else ""
                    )
                    event_data_raw = event.get("data")
                    event_data = (
                        event_data_raw if isinstance(event_data_raw, dict) else {}
                    )
                    sse_line = await processor.on_event(event_type, event_data)
                    if sse_line:
                        yield sse_line
                for extra in await processor.finalize():
                    yield extra
            except Exception as e:
                yield await processor.handle_exception(e)

        return plan_event_generator()

    # Default: executor mode (strategy-bound)
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
        mode=cast(ChatMode, mode),
        provider_override=provider_override,
        model_override=effective_model,
        reasoning_effort=reasoning_effort,
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
            mode=mode,
        )
        try:
            yield processor.start_event()

            stream_iter = (
                _mock_stream_chat(
                    mode=mode,
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
