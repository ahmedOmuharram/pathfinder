"""Fail if packages/spec/openapi.yaml is out of date."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml


def main() -> int:
    repo_root = Path(__file__).resolve().parents[3]
    api_src = repo_root / "apps" / "api" / "src"
    sys.path.insert(0, str(api_src))

    from veupath_chatbot.main import create_app

    app = create_app()
    actual = app.openapi()

    # Must match generate_openapi_yaml.py behavior exactly.
    actual.setdefault("openapi", "3.1.0")
    actual.setdefault(
        "servers",
        [
            {"url": "http://localhost:8000", "description": "Local development"},
            {"url": "https://api.pathfinder.veupathdb.org", "description": "Production"},
        ],
    )

    openapi_path = repo_root / "packages" / "spec" / "openapi.yaml"
    if not openapi_path.exists():
        print(f"Missing {openapi_path}. Run generate_openapi_yaml.py first.")
        return 1

    current_text = openapi_path.read_text("utf-8")
    expected_text = yaml.safe_dump(
        actual,
        sort_keys=False,
        allow_unicode=True,
        width=120,
    )

    if current_text != expected_text:
        print("OpenAPI spec is out of date.")
        print("Run: (cd apps/api && uv run python scripts/generate_openapi_yaml.py)")
        return 1

    print("OpenAPI spec is up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

