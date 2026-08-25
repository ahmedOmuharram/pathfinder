"""A credentialed tool source is refused until a deployment configures one."""

from __future__ import annotations

import pytest
from assistant_core.mcp.admission import AdmissionRecord
from assistant_core.mcp.resolution import ToolSourceUnavailableError

from pathfinder.ai.conversation.turn_runner import deployment_credential


def test_a_credentialed_source_is_refused_loudly() -> None:
    record = AdmissionRecord(
        source_id="eda",
        endpoint="https://eda.example.org/mcp",
        credential_mode="service",
        part_namespace="eda",
    )

    with pytest.raises(ToolSourceUnavailableError, match="eda"):
        deployment_credential(record)
