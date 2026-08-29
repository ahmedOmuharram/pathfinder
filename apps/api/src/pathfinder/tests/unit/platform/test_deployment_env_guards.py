"""Every process but the api is switched off from the writes the api owns.

A process that rebuilds a catalog or syncs an embedding index races the api, so
every deployment description of the worker and of wdk-mcp carries the guards.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[7]
_QUADLETS = _REPO_ROOT / "quadlets"
_WORKER_QUADLET = _QUADLETS / "pathfinder-worker.container"
_MCP_QUADLET = _QUADLETS / "pathfinder-wdk-mcp.container"
_COMPOSE = _REPO_ROOT / "docker-compose.yml"

_ENV_PREFIX = "Environment="

# The writes only the api may make.
_GUARDS = {
    "CATALOG_REFRESH_ENABLED": "false",
    "EMBEDDING_INDEX_SYNC_ENABLED": "false",
}

# Every unit that must carry them, and the compose service beside it.
_GUARDED_UNITS = (_WORKER_QUADLET, _MCP_QUADLET)
_GUARDED_SERVICES = ("worker", "wdk-mcp")

# Tunables the operator sets. A quadlet Environment= would beat its own
# EnvironmentFile, so pinning one here would take that away.
_NOT_PINNED = ("WORKER_DEAD_HEARTBEAT_SECONDS", "WORKER_STALLED_JOB_TIMEOUT_SECONDS")


def _quadlet_environment(unit: Path) -> dict[str, str]:
    """The literal ``Environment=KEY=VALUE`` pairs a unit declares."""
    pairs: dict[str, str] = {}
    for line in unit.read_text().splitlines():
        stripped = line.strip()
        if not stripped.startswith(_ENV_PREFIX):
            continue
        key, _, value = stripped.removeprefix(_ENV_PREFIX).partition("=")
        pairs[key] = value
    return pairs


def _compose_environment(service: str) -> dict[str, str]:
    document: dict[str, Any] = yaml.safe_load(_COMPOSE.read_text())
    environment: dict[str, str] = document["services"][service]["environment"]
    return environment


@pytest.mark.parametrize("unit", _GUARDED_UNITS, ids=lambda unit: unit.name)
def test_every_guarded_quadlet_pins_every_write_guard(unit: Path) -> None:
    environment = _quadlet_environment(unit)

    assert {key: environment.get(key) for key in _GUARDS} == _GUARDS


@pytest.mark.parametrize("service", _GUARDED_SERVICES)
def test_every_guarded_compose_service_pins_the_same_guards(service: str) -> None:
    environment = _compose_environment(service)

    assert {key: environment.get(key) for key in _GUARDS} == _GUARDS


def test_the_api_is_the_process_that_syncs() -> None:
    """The guards mean nothing unless exactly one process is allowed to write."""
    assert _compose_environment("api")["EMBEDDING_INDEX_SYNC_ENABLED"] == "true"


def test_the_worker_quadlet_leaves_the_tunables_to_the_environment_file() -> None:
    """Compose passes these through with a default; the quadlet must not pin them."""
    environment = _quadlet_environment(_WORKER_QUADLET)

    assert [key for key in _NOT_PINNED if key in environment] == []


def test_compose_passes_the_tunables_through_rather_than_hardcoding_them() -> None:
    environment = _compose_environment("worker")

    for key in _NOT_PINNED:
        assert environment[key].startswith(f"${{{key}:-")


@pytest.mark.parametrize("unit", _GUARDED_UNITS, ids=lambda unit: unit.name)
def test_every_guarded_quadlet_reads_its_environment_file_first(unit: Path) -> None:
    """The guards override the file, so the file has to be read first."""
    lines = [line.strip() for line in unit.read_text().splitlines()]
    env_file = next(
        i for i, line in enumerate(lines) if line.startswith("EnvironmentFile=")
    )
    first_guard = next(
        i
        for i, line in enumerate(lines)
        if line.startswith(_ENV_PREFIX)
        and line.removeprefix(_ENV_PREFIX).partition("=")[0] in _GUARDS
    )
    assert env_file < first_guard
