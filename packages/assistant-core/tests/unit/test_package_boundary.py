"""The boundary is an installation fact; this suite is the belt.

The package declares no dependency on ``pathfinder``, so a science import
cannot resolve. The walk below fails on the import statement instead of on
the missing distribution, and names the module that added it.
"""

from __future__ import annotations

import ast
import importlib
import pkgutil
from pathlib import Path
from types import ModuleType

import pytest

import assistant_core

CORE = assistant_core.__name__

# The runtime shares the wire types the client also reads. Nothing else.
ALLOWED_SHARED = {
    "shared_py.stream_parts.background_task",
    "shared_py.stream_parts.turn_usage",
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


def _imported_names(module: ModuleType) -> set[str]:
    path = module.__file__
    assert path is not None
    names: set[str] = set()
    for node in ast.walk(ast.parse(Path(path).read_text())):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
        elif isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
    return names


@pytest.mark.parametrize("module", _core_modules(), ids=lambda m: m.__name__)
def test_no_runtime_module_imports_the_science(module: ModuleType) -> None:
    reached = {
        name for name in _imported_names(module) if name.startswith("pathfinder")
    }

    assert reached == set()


def test_the_shared_types_the_runtime_reads_have_not_grown() -> None:
    reached = {
        name
        for m in _core_modules()
        for name in _imported_names(m)
        if name.startswith("shared_py")
    }

    assert reached == ALLOWED_SHARED
