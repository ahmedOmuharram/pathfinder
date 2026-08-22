"""The boundary that keeps the runtime extractable.

``assistant_core`` is the half a second assistant reuses. It may reach the
platform, the event tables and the embedding model, and nothing else, so
lifting it out stays a move of one directory.
"""

from __future__ import annotations

import ast
import importlib
import pkgutil
from pathlib import Path
from types import ModuleType

import pytest

from pathfinder import assistant_core

CORE = assistant_core.__name__

ALLOWED_OUTSIDE = {
    "pathfinder.integrations.embeddings.model",
    "pathfinder.integrations.embeddings.prefixes",
    "pathfinder.persistence.models",
    "pathfinder.platform.config",
    "pathfinder.platform.context",
    "pathfinder.platform.db",
    "pathfinder.platform.logging",
    "pathfinder.platform.pydantic_base",
    "pathfinder.platform.types",
}


def _core_modules() -> list[ModuleType]:
    return [
        assistant_core,
        *(
            importlib.import_module(info.name)
            for info in pkgutil.walk_packages(
                assistant_core.__path__,
                prefix=f"{CORE}.",
            )
        ),
    ]


def _imports_outside_core(module: ModuleType) -> set[str]:
    path = module.__file__
    assert path is not None
    names: set[str] = set()
    for node in ast.walk(ast.parse(Path(path).read_text())):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
        elif isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
    return {
        name
        for name in names
        if name.startswith("pathfinder") and not name.startswith(f"{CORE}.")
    }


@pytest.mark.parametrize("module", _core_modules(), ids=lambda m: m.__name__)
def test_no_runtime_module_imports_the_science(module: ModuleType) -> None:
    assert _imports_outside_core(module) <= ALLOWED_OUTSIDE


def test_the_surface_the_runtime_reaches_outside_itself_has_not_grown() -> None:
    reached = {name for m in _core_modules() for name in _imports_outside_core(m)}
    assert reached == ALLOWED_OUTSIDE
