"""The generated spec is the production contract, whatever the process env."""

import pytest

from pathfinder.devtools.openapi import _spec_with_stable_overrides
from pathfinder.platform.config import get_settings


def test_the_spec_never_carries_dev_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "pathfinder_chat_provider", "mock")

    spec = _spec_with_stable_overrides()

    dev_paths = [p for p in spec["paths"] if p.startswith("/api/v1/dev/")]
    assert dev_paths == []
