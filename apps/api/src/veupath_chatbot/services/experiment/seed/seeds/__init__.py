"""Per-database seed definitions."""

import contextlib
from importlib import import_module
from typing import Any

# Available seed databases
SEED_DATABASES: list[str] = [
    "plasmodb",
    "toxodb",
    "cryptodb",
    "piroplasmadb",
    "tritrypdb",
    "fungidb",
    "vectorbase",
    "giardiadb",
    "amoebadb",
    "microsporidiadb",
    "hostdb",
    "veupathdb",
    "orthomcl",
]


def get_seeds_for_site(site_id: str) -> list[Any]:
    """Import and return SEEDS for a specific site."""
    mod = import_module(f".{site_id}", package=__name__)
    seeds: list[Any] = mod.SEEDS
    return seeds


def get_all_seeds() -> list[Any]:
    """Get seeds for all available sites."""
    all_seeds: list[Any] = []
    for site_id in SEED_DATABASES:
        with contextlib.suppress(ImportError, AttributeError):
            all_seeds.extend(get_seeds_for_site(site_id))
    return all_seeds
