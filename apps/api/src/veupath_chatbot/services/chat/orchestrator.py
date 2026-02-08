"""Chat orchestration entrypoint (service layer).

Implementation details are split across smaller modules. The HTTP layer should
call `start_chat_stream` and remain thin.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timezone
from uuid import UUID

from kani import ChatMessage, ChatRole

from veupath_chatbot.ai.agent_factory import create_agent
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.security import create_user_token
from veupath_chatbot.persistence.repo import (
    PlanSessionRepository,
    StrategyRepository,
    UserRepository,
)
from veupath_chatbot.transport.http.streaming import stream_chat

from veupath_chatbot.services.chat.bootstrap import (
    append_user_message,
    build_chat_history,
    build_strategy_payload,
    ensure_strategy,
    ensure_user,
)
from veupath_chatbot.services.chat.processor import ChatStreamProcessor
from veupath_chatbot.services.chat.plan_processor import PlanStreamProcessor
from veupath_chatbot.services.chat.utils import parse_selected_nodes

logger = get_logger(__name__)


async def start_chat_stream(
    *,
    message: str,
    site_id: str,
    strategy_id: UUID | None,
    plan_session_id: UUID | None,
    mode: str = "execute",
    user_id: UUID | None,
    user_repo: UserRepository,
    strategy_repo: StrategyRepository,
    plan_repo: PlanSessionRepository,
) -> tuple[str, AsyncIterator[str]]:
    """Start an SSE stream for a chat turn.

    Returns `(auth_token, sse_iterator)` where `sse_iterator` yields SSE-formatted strings.
    """
    user_id = await ensure_user(user_repo, user_id)
    auth_token = create_user_token(user_id)

    if mode == "plan":
        # Plan sessions are not strategies; do not create/modify the strategy sidebar.
        # If a plan session id is not provided, create a new one.
        plan_session = (
            await plan_repo.get_by_id(plan_session_id) if plan_session_id else None
        )
        if plan_session is None:
            plan_session = await plan_repo.create(user_id=user_id, site_id=site_id, title="Plan")

        user_message = {
            "role": "user",
            "content": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await plan_repo.add_message(plan_session.id, user_message)
        await plan_repo.clear_thinking(plan_session.id)

        # For planning mode we do not support node-selection encoding (graph-less), but we
        # still strip it if present so the model sees clean text.
        _, model_message = parse_selected_nodes(message)

        await plan_repo.refresh(plan_session)
        history: list[ChatMessage] = []
        for msg in plan_session.messages or []:
            role = msg.get("role")
            content = msg.get("content")
            if not content:
                continue
            if role == "user":
                _, cleaned = parse_selected_nodes(content)
                history.append(ChatMessage(role=ChatRole.USER, content=cleaned))
            elif role == "assistant":
                history.append(ChatMessage(role=ChatRole.ASSISTANT, content=content))

        async def _get_plan_artifacts() -> list[dict]:
            ps = await plan_repo.get_by_id(plan_session.id)
            return (ps.planning_artifacts or []) if ps else []

        # Provide the latest saved delegation draft (if any) directly in the planner's
        # system prompt so the model doesn't need to "remember" via extra tool calls.
        delegation_draft_artifact: dict | None = None
        for a in (plan_session.planning_artifacts or []):
            if isinstance(a, dict) and a.get("id") == "delegation_draft":
                delegation_draft_artifact = a
                break

        agent = create_agent(
            site_id=site_id,
            user_id=user_id,
            chat_history=history,
            strategy_graph=None,
            selected_nodes=None,
            delegation_draft_artifact=delegation_draft_artifact,
            plan_session_id=plan_session.id,
            get_plan_session_artifacts=_get_plan_artifacts,
            mode="plan",
        )

        plan_payload = {
            "id": str(plan_session.id),
            "siteId": plan_session.site_id,
            "title": plan_session.title,
        }

        async def plan_event_generator() -> AsyncIterator[str]:
            processor = PlanStreamProcessor(
                plan_repo=plan_repo,
                user_id=user_id,
                plan_session=plan_session,
                auth_token=auth_token,
                plan_payload=plan_payload,
                mode=mode,
            )
            try:
                yield processor.start_event()
                async for event in stream_chat(agent, model_message):
                    event_type = event.get("type", "")
                    event_data = event.get("data", {}) or {}
                    sse_line = await processor.on_event(event_type, event_data)
                    if sse_line:
                        yield sse_line
                for extra in await processor.finalize():
                    yield extra
            except Exception as e:
                yield await processor.handle_exception(e)

        return auth_token, plan_event_generator()

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
    strategy_graph_payload = {
        "id": strategy.id,
        "name": strategy.name,
        "plan": strategy.plan,
        "steps": strategy.steps,
        "rootStepId": strategy.root_step_id,
        "recordType": strategy.record_type,
    }

    agent = create_agent(
        site_id=site_id,
        user_id=user_id,
        chat_history=history,
        strategy_graph=strategy_graph_payload,
        selected_nodes=selected_nodes,
        mode=mode,
    )

    async def event_generator() -> AsyncIterator[str]:
        processor = ChatStreamProcessor(
            strategy_repo=strategy_repo,
            site_id=site_id,
            user_id=user_id,
            strategy=strategy,
            auth_token=auth_token,
            strategy_payload=strategy_payload,
            mode=mode,
        )
        try:
            yield processor.start_event()

            async for event in stream_chat(agent, model_message):
                event_type = event.get("type", "")
                event_data = event.get("data", {}) or {}
                sse_line = await processor.on_event(event_type, event_data)
                if sse_line:
                    yield sse_line

            for extra in await processor.finalize():
                yield extra
        except Exception as e:
            yield await processor.handle_exception(e)

    return auth_token, event_generator()

