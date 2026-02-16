from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from veupath_chatbot.services.chat.processor import ChatStreamProcessor


class _FakeSession:
    def __init__(self) -> None:
        self.commit_calls = 0

    async def commit(self) -> None:
        self.commit_calls += 1


class _FakeStrategyRepo:
    def __init__(self) -> None:
        self.session = _FakeSession()
        self.updated: list[dict] = []
        self.created: list[dict] = []

    async def update(self, strategy_id, **kwargs):
        self.updated.append({"strategy_id": strategy_id, **kwargs})
        return SimpleNamespace(id=strategy_id)

    async def create(self, **kwargs):
        self.created.append(kwargs)
        return None

    async def update_thinking(self, strategy_id, payload):
        return None

    async def clear_thinking(self, strategy_id):
        return None

    async def add_message(self, strategy_id, message):
        return None


@pytest.mark.asyncio
async def test_strategy_link_updates_active_strategy_and_commits_mid_stream() -> None:
    repo = _FakeStrategyRepo()
    current_strategy_id = uuid4()
    strategy = SimpleNamespace(id=current_strategy_id, wdk_strategy_id=None)
    processor = ChatStreamProcessor(
        strategy_repo=repo,
        site_id="plasmodb",
        user_id=uuid4(),
        strategy=strategy,
        strategy_payload={"id": str(current_strategy_id)},
        mode="execute",
    )

    other_graph_id = str(uuid4())
    line = await processor.on_event(
        "strategy_link",
        {"graphId": other_graph_id, "wdkStrategyId": 12345, "name": "Built strategy"},
    )

    assert line is not None
    assert len(repo.updated) == 1
    assert repo.updated[0]["strategy_id"] == current_strategy_id
    assert repo.updated[0]["wdk_strategy_id"] == 12345
    assert repo.updated[0]["wdk_strategy_id_set"] is True
    assert repo.created == []
    assert repo.session.commit_calls == 1
    assert processor.pending_strategy_link[str(current_strategy_id)]["graphId"] == str(
        current_strategy_id
    )
