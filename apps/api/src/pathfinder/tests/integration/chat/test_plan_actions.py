"""Integration tests for dedicated structured plan actions."""

import json
from uuid import UUID, uuid4

import httpx
import pytest

import pathfinder.persistence.session as session_module
from pathfinder.domain.strategy.plan import (
    ParamStatus,
    PlannedParameter,
    PlannedStep,
    PlanStatus,
    StepStatus,
    StepType,
    StrategyPlan,
    UserQuestion,
)
from pathfinder.persistence.models import User
from pathfinder.persistence.repositories import PlanRepository, StreamRepository
from pathfinder.persistence.repositories.stream import ProjectionUpdate
from pathfinder.platform.redis import get_redis
from pathfinder.platform.security import create_user_token
from pathfinder.platform.types import JSONObject


async def _create_presented_plan_stream(*, user_id: UUID) -> tuple[str, str]:
    async with session_module.async_session_factory() as session:
        session.add(User(id=user_id))
        await session.flush()

        stream_repo = StreamRepository(session)
        stream = await stream_repo.create(
            user_id=user_id,
            site_id="plasmodb",
            name="Approval Test Strategy",
        )
        await stream_repo.update_projection(
            stream.id,
            ProjectionUpdate(
                name="Approval Test Strategy",
                record_type="transcript",
            ),
        )

        plan = StrategyPlan(
            id="plan_approval_test",
            title="Approval Test Plan",
            description="A plan that needs one answer and one param edit.",
            rationale="Exercise the dedicated approval route.",
            status=PlanStatus.PRESENTED,
            steps=[
                PlannedStep(
                    id="step_taxon",
                    search_name="GenesByTaxon",
                    display_name="Genes by Taxon",
                    record_type="transcript",
                    rationale="Start from the selected organism.",
                    step_type=StepType.LEAF,
                    status=StepStatus.NEEDS_USER_INPUT,
                    parameters={
                        "organism": PlannedParameter(
                            name="organism",
                            display_name="Organism",
                            param_type="multi-pick-vocabulary",
                            value=None,
                            status=ParamStatus.NEEDS_USER_INPUT,
                            required=True,
                            question="Which organism should we use?",
                        ),
                    },
                ),
            ],
            connections=[],
            questions=[
                UserQuestion(
                    id="q_species",
                    question="Which organism should we use?",
                    related_step="step_taxon",
                    related_param="organism",
                ),
            ],
        )

        plan_repo = PlanRepository(session)
        await plan_repo.save_plan(plan, stream.id)
        await session.commit()
        return str(stream.id), plan.id


async def _collect_operation_events(
    client: httpx.AsyncClient,
    *,
    operation_id: str,
) -> list[JSONObject]:
    events: list[JSONObject] = []
    buffer = ""

    async with client.stream(
        "GET",
        f"/api/v1/operations/{operation_id}/subscribe",
        timeout=30.0,
    ) as response:
        assert response.status_code == 200
        async for chunk in response.aiter_text():
            buffer += chunk
            while "\n\n" in buffer:
                raw, buffer = buffer.split("\n\n", 1)
                part = raw.strip()
                if not part:
                    continue
                event_type: str | None = None
                data_raw: str | None = None
                for line in part.splitlines():
                    if line.startswith("event:"):
                        event_type = line.removeprefix("event:").strip()
                    elif line.startswith("data:"):
                        data_raw = line.removeprefix("data:").strip()
                if not event_type or data_raw is None:
                    continue
                data = json.loads(data_raw)
                if not isinstance(data, dict):
                    continue
                events.append({"type": event_type, "data": data})
                if event_type == "message_end":
                    return events

    return events


@pytest.mark.asyncio
async def test_approve_plan_action_emits_plan_approved_without_user_message(
    client: httpx.AsyncClient,
) -> None:
    user_id = uuid4()
    client.cookies.set("pathfinder-auth", create_user_token(user_id))

    strategy_id, plan_id = await _create_presented_plan_stream(user_id=user_id)

    response = await client.post(
        f"/api/v1/strategies/{strategy_id}/plan-actions",
        json={
            "action": "approve",
            "planId": plan_id,
            "paramEdits": [
                {
                    "stepId": "step_taxon",
                    "paramName": "organism",
                    "newValue": ["Plasmodium falciparum 3D7"],
                }
            ],
            "answers": [
                {
                    "questionId": "q_species",
                    "answer": "Plasmodium falciparum 3D7",
                }
            ],
        },
        timeout=30.0,
    )

    assert response.status_code == 202
    body = response.json()
    assert body["strategyId"] == strategy_id
    operation_id = body["operationId"]

    events = await _collect_operation_events(client, operation_id=operation_id)
    event_types = [event["type"] for event in events]

    assert "plan_approved" in event_types
    assert "plan_updated" in event_types
    assert any(
        event["type"] == "phase_change"
        and event["data"].get("phase") == "execution"
        and event["data"].get("status") == "started"
        for event in events
    )
    execution_started = next(
        event["data"]
        for event in events
        if event["type"] == "phase_change"
        and event["data"].get("phase") == "execution"
        and event["data"].get("status") == "started"
    )
    assert isinstance(execution_started.get("emittedAt"), str)
    assert isinstance(execution_started.get("phaseStartedAt"), str)
    assert execution_started.get("phaseCompletedAt") is None
    assert execution_started.get("durationMs") == 0

    approved = next(event for event in events if event["type"] == "plan_approved")
    approved_plan = approved["data"]["plan"]
    assert approved["data"]["planId"] == plan_id
    assert approved_plan["status"] == "approved"
    assert approved_plan["questions"][0]["answer"] == "Plasmodium falciparum 3D7"
    assert (
        approved_plan["steps"][0]["parameters"]["organism"]["value"]
        == ["Plasmodium falciparum 3D7"]
    )

    plan_updates = [
        event["data"]["updates"]
        for event in events
        if event["type"] == "plan_updated"
    ]
    assert any(update.get("status") == "executing" for update in plan_updates)
    assert any(update.get("status") == "complete" for update in plan_updates)

    entries = await get_redis().xrange(f"stream:{strategy_id}")
    stream_event_types = [fields.get("type", "") for _entry_id, fields in entries]
    assert "user_message" not in stream_event_types

    async with session_module.async_session_factory() as session:
        restored = await PlanRepository(session).get_latest_plan(UUID(strategy_id))
        assert restored is not None
        assert restored.status == PlanStatus.COMPLETE
        assert restored.questions[0].answer == "Plasmodium falciparum 3D7"
        assert restored.steps[0].parameters["organism"].value == [
            "Plasmodium falciparum 3D7"
        ]
        assert restored.steps[0].status == StepStatus.COMPLETE
