"""Generate OpenAPI YAML from the FastAPI app.

This keeps `packages/spec/openapi.yaml` aligned with the actual running API.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml


def main() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    api_src = repo_root / "apps" / "api" / "src"
    sys.path.insert(0, str(api_src))

    # Import from the app factory so we include all routers/middleware consistently.
    from veupath_chatbot.main import create_app

    app = create_app()
    spec = app.openapi()

    # Keep a stable OAS version string if FastAPI omits/changes it.
    spec.setdefault("openapi", "3.1.0")

    # Preserve/define servers (helps local dev + prod docs).
    spec.setdefault(
        "servers",
        [
            {"url": "http://localhost:8000", "description": "Local development"},
            {"url": "https://api.pathfinder.veupathdb.org", "description": "Production"},
        ],
    )

    out_path = repo_root / "packages" / "spec" / "openapi.yaml"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(
            spec,
            f,
            sort_keys=False,
            allow_unicode=True,
            width=120,
        )

    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()

