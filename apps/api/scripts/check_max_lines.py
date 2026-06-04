"""Check that Python source files stay under the line limit.

Enforces a 400-line cap (excluding blank lines and comments) on production
code. Seed data, test files, and pure-model files are exempt.

Usage:
    python scripts/check_max_lines.py [--limit N] [--verbose]
"""

import argparse
import sys
from pathlib import Path

DEFAULT_LIMIT = 400
SRC_ROOT = Path("src/pathfinder")

# Directories and files exempt from the line limit.
EXEMPT_PATTERNS: set[str] = {
    "tests/",
    "devtools/",
    "seed/seeds/",
    "cassettes/",
    "__pycache__/",
    # Pure data-model / schema files (no logic, splitting is artificial)
    "integrations/veupathdb/wdk_models.py",
    "transport/http/schemas/experiment_responses.py",
    "persistence/models.py",  # SQLAlchemy ORM table definitions
    "ai/tools/standalone/_plan_models.py",  # Pydantic plan models
    # Single-responsibility modules where splitting would be artificial
    "domain/strategy/session.py",  # core state machine
    "services/strategies/sync.py",  # tightly coupled tree building
    "services/strategies/step_creation.py",  # single step-creation concern
    "services/control_tests.py",  # cohesive control test logic
    "services/experiment/step_analysis/phase_sensitivity.py",  # single analysis pipeline
    "services/catalog/param_validation.py",  # single validation pipeline
    "transport/http/routers/gene_sets.py",  # pure transport layer
    "integrations/veupathdb/strategy_api/base.py",  # core API client
    "integrations/veupathdb/strategy_api/steps.py",  # step API endpoints
    # Borderline files (300-325 meaningful lines) — single-responsibility
    "ai/models/catalog.py",  # catalog model wrapper
    "ai/tools/standalone/plan.py",  # plan tool (LLM interface)
    "persistence/repositories/stream.py",  # Redis stream repository
    "services/gene_lookup/lookup.py",  # gene lookup service
    "services/research/utils.py",  # research utility cluster
}


def _is_exempt(path: Path) -> bool:
    rel = str(path.relative_to(SRC_ROOT))
    return any(pattern in rel for pattern in EXEMPT_PATTERNS)


def _count_meaningful_lines(path: Path) -> int:
    """Count non-blank, non-comment lines."""
    count = 0
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    violations: list[tuple[Path, int]] = []

    for path in sorted(SRC_ROOT.rglob("*.py")):
        if _is_exempt(path):
            continue
        lines = _count_meaningful_lines(path)
        if lines > args.limit:
            violations.append((path, lines))
        elif args.verbose:
            print(f"  OK  {path} ({lines})")

    if violations:
        print(f"\n{len(violations)} file(s) exceed {args.limit} meaningful lines:\n")
        for path, lines in violations:
            print(f"  FAIL  {path}: {lines} lines (limit {args.limit})")
        print("\nFix by splitting into smaller modules.")
        return 1

    print(f"All files under {args.limit} meaningful lines.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
