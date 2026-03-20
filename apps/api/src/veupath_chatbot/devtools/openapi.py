"""Developer tooling for keeping OpenAPI spec in sync.

This is intentionally NOT run by the API at runtime. It writes repo files.
"""

import argparse
from pathlib import Path

import yaml

from veupath_chatbot.main import create_app
from veupath_chatbot.platform.types import JSONObject


def _repo_root() -> Path:
    # .../apps/api/src/veupath_chatbot/devtools/openapi.py -> repo root
    return Path(__file__).resolve().parents[5]


def _spec_with_stable_overrides() -> JSONObject:
    app = create_app()
    spec = app.openapi()

    # Keep a stable OAS version string if FastAPI omits/changes it.
    spec.setdefault("openapi", "3.1.0")

    # Preserve/define servers (helps local dev).
    spec.setdefault(
        "servers",
        [
            {"url": "http://localhost:8000", "description": "Local development"},
        ],
    )
    return spec


def generate_openapi_yaml(*, out_path: Path | None = None) -> Path:
    root = _repo_root()
    path = out_path or (root / "packages" / "spec" / "openapi.yaml")
    path.parent.mkdir(parents=True, exist_ok=True)

    spec = _spec_with_stable_overrides()
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(
            spec,
            f,
            sort_keys=False,
            allow_unicode=True,
            width=120,
        )
    return path


def check_openapi_yaml(*, openapi_path: Path | None = None) -> bool:
    root = _repo_root()
    path = openapi_path or (root / "packages" / "spec" / "openapi.yaml")
    if not path.exists():
        msg = f"Missing {path}. Run generate first."
        raise FileNotFoundError(msg)

    actual = _spec_with_stable_overrides()
    expected_text = yaml.safe_dump(
        actual,
        sort_keys=False,
        allow_unicode=True,
        width=120,
    )
    current_text = path.read_text("utf-8")
    return current_text == expected_text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser(
        "generate", help="Write packages/spec/openapi.yaml from the FastAPI app"
    )
    sub.add_parser(
        "check", help="Exit non-zero if packages/spec/openapi.yaml is out of date"
    )
    args = parser.parse_args(argv)

    if args.cmd == "generate":
        generate_openapi_yaml()
        return 0

    ok = check_openapi_yaml()
    if not ok:
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
