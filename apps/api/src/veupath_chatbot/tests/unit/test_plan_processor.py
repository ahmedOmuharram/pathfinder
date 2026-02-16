from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from veupath_chatbot.services.chat.plan_processor import PlanStreamProcessor


class _FakePlanRepo:
    def __init__(self) -> None:
        self.messages: list[dict] = []
        self.thinking_updates: list[dict] = []

    async def update_thinking(self, plan_session_id, payload):
        self.thinking_updates.append(payload)

    async def clear_thinking(self, plan_session_id):
        return None

    async def update_title(self, plan_session_id, user_id, title):
        return None

    async def add_message(self, plan_session_id, msg):
        self.messages.append(msg)

    async def append_planning_artifacts(self, plan_session_id, artifacts):
        return None


class _FakePlanSession:
    def __init__(self) -> None:
        self.id = uuid4()
        self.site_id = "plasmodb"
        self.title = "Plan"
        self.messages = []
        self.planning_artifacts = []
        self.thinking = None
        self.model_id = None
        self.created_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)


@pytest.mark.asyncio
async def test_plan_processor_persists_optimization_progress_on_final_message() -> None:
    repo = _FakePlanRepo()
    plan = _FakePlanSession()
    processor = PlanStreamProcessor(
        plan_repo=repo,
        user_id=uuid4(),
        plan_session=plan,
        plan_payload={"id": str(plan.id), "siteId": plan.site_id, "title": plan.title},
        mode="plan",
    )

    await processor.on_event(
        "optimization_progress",
        {
            "optimizationId": "opt-1",
            "status": "running",
            "currentTrial": 2,
            "totalTrials": 10,
        },
    )
    await processor.on_event(
        "assistant_message",
        {"content": "Running optimization now."},
    )
    await processor.finalize()

    assert len(repo.messages) == 1
    assert repo.messages[0].get("optimizationProgress") == {
        "optimizationId": "opt-1",
        "status": "running",
        "currentTrial": 2,
        "totalTrials": 10,
    }
