from __future__ import annotations

import importlib.util
from pathlib import Path


def _module_source(dotted: str) -> str:
    spec = importlib.util.find_spec(dotted)
    assert spec is not None
    assert spec.origin is not None
    return Path(spec.origin).read_text()


def test_discovery_does_not_import_services() -> None:
    """Integration layer must not reach up into services."""
    source = _module_source("pathfinder.integrations.veupathdb.discovery")
    assert "pathfinder.services" not in source


def test_semantic_index_lives_in_integrations() -> None:
    spec = importlib.util.find_spec(
        "pathfinder.integrations.embeddings.semantic_index",
    )
    assert spec is not None
