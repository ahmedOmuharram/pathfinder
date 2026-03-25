#!/usr/bin/env python3
"""Trim large arrays in VCR cassette YAML files to reduce size.

Parses the JSON inside each response body, recursively truncates arrays
exceeding --max-items, and writes the trimmed YAML back.

Usage:
    uv run python scripts/trim_cassettes.py --dry-run
    uv run python scripts/trim_cassettes.py
    uv run python scripts/trim_cassettes.py --max-items 10 --cassette-dir path/to/cassettes
"""

import argparse
import json
import sys
from pathlib import Path

import yaml  # third-party

_BYTES_PER_MB = 1_000_000
_BYTES_PER_KB = 1_000


# ---------------------------------------------------------------------------
# Core trimming logic
# ---------------------------------------------------------------------------


def _trim_large_arrays(obj: object, max_items: int = 50) -> object:
    """Recursively truncate arrays longer than max_items."""
    if isinstance(obj, list):
        return [_trim_large_arrays(item, max_items) for item in obj[:max_items]]
    if isinstance(obj, dict):
        return {k: _trim_large_arrays(v, max_items) for k, v in obj.items()}
    return obj


def _try_trim_body_string(body_string: str, max_items: int) -> str | None:
    """Parse JSON body, trim arrays, re-serialize. Returns None if unchanged."""
    stripped = body_string.strip()
    if not stripped or stripped[0] not in ("{", "["):
        return None

    try:
        parsed = json.loads(body_string)
    except (json.JSONDecodeError, ValueError):
        return None

    trimmed = _trim_large_arrays(parsed, max_items)
    new_body_string = json.dumps(trimmed, separators=(",", ":"))

    if new_body_string == body_string:
        return None
    return new_body_string


def _trim_interaction(interaction: dict, max_items: int) -> bool:
    """Trim JSON arrays inside a single VCR interaction's response body.

    Returns True if the body was modified.
    """
    body_string = (
        interaction.get("response", {}).get("body", {}).get("string")
    )
    if not body_string or not isinstance(body_string, str):
        return False

    new_body = _try_trim_body_string(body_string, max_items)
    if new_body is None:
        return False

    interaction["response"]["body"]["string"] = new_body
    return True


def _trim_cassette(data: dict, max_items: int) -> bool:
    """Trim all interactions in a parsed cassette. Returns True if anything changed."""
    interactions = data.get("interactions")
    if not interactions or not isinstance(interactions, list):
        return False

    changed = False
    for interaction in interactions:
        if _trim_interaction(interaction, max_items):
            changed = True
    return changed


# ---------------------------------------------------------------------------
# File processing
# ---------------------------------------------------------------------------


def _format_size(size_bytes: int) -> str:
    """Format byte count as human-readable string."""
    if size_bytes >= _BYTES_PER_MB:
        return f"{size_bytes / _BYTES_PER_MB:.1f}MB"
    if size_bytes >= _BYTES_PER_KB:
        return f"{size_bytes / _BYTES_PER_KB:.1f}KB"
    return f"{size_bytes}B"


def _process_file(
    path: Path,
    max_items: int,
    *,
    dry_run: bool,
) -> tuple[int, int]:
    """Process a single cassette file. Returns (original_size, new_size)."""
    original_size = path.stat().st_size
    text = path.read_text(encoding="utf-8")

    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        print(f"  WARNING: Skipping {path.name} (YAML parse error: {exc})")
        return original_size, original_size
    if not data:
        return original_size, original_size

    changed = _trim_cassette(data, max_items)
    if not changed:
        return original_size, original_size

    new_text = yaml.dump(
        data,
        default_flow_style=False,
        allow_unicode=True,
        width=_BYTES_PER_MB,  # prevent line wrapping of long JSON strings
    )
    new_size = len(new_text.encode("utf-8"))

    if not dry_run:
        path.write_text(new_text, encoding="utf-8")
        new_size = path.stat().st_size

    return original_size, new_size


def _process_directory(
    cassette_dir: Path,
    max_items: int,
    *,
    dry_run: bool,
) -> None:
    """Process all YAML cassettes in the directory."""
    yaml_files = sorted(cassette_dir.glob("*.yaml"))
    if not yaml_files:
        print(f"WARNING: No .yaml files found in {cassette_dir}")
        return

    mode_label = "[DRY RUN] " if dry_run else ""
    print(
        f"{mode_label}Trimming {len(yaml_files)} cassettes "
        f"(max_items={max_items})...\n"
    )

    total_original = 0
    total_new = 0
    files_changed = 0

    for path in yaml_files:
        original_size, new_size = _process_file(
            path, max_items, dry_run=dry_run,
        )
        total_original += original_size
        total_new += new_size

        if original_size != new_size:
            files_changed += 1
            reduction_pct = (
                (1 - new_size / original_size) * 100
                if original_size > 0
                else 0
            )
            print(
                f"  {path.name}: "
                f"{_format_size(original_size)} -> "
                f"{_format_size(new_size)} "
                f"(-{reduction_pct:.0f}%)"
            )

    # Summary
    print(f"\n{mode_label}Files changed: {files_changed}/{len(yaml_files)}")
    if total_original > 0:
        total_pct = (1 - total_new / total_original) * 100
        print(
            f"{mode_label}Total: "
            f"{_format_size(total_original)} -> "
            f"{_format_size(total_new)} "
            f"(-{total_pct:.0f}%)"
        )
    else:
        print(f"{mode_label}Total: 0B (no cassettes)")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Trim large arrays in VCR cassette YAML files",
    )
    parser.add_argument(
        "--cassette-dir",
        type=Path,
        default=Path("src/veupath_chatbot/tests/cassettes"),
        help=(
            "Path to cassettes directory "
            "(default: src/veupath_chatbot/tests/cassettes)"
        ),
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=25,
        help="Maximum number of items to keep in arrays (default: 25)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would change without writing files",
    )
    args = parser.parse_args()

    cassette_dir: Path = args.cassette_dir
    if not cassette_dir.is_dir():
        print(f"ERROR: {cassette_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    _process_directory(cassette_dir, args.max_items, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
