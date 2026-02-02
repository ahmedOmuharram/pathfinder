#!/usr/bin/env python3
"""Generate JSON Schema from Pydantic models."""

import json
from pathlib import Path

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from veupath_chatbot.api.schemas import (
    ChatRequest,
    CreateStrategyRequest,
    StrategyResponse,
    PreviewRequest,
    DownloadRequest,
)


def main():
    """Generate JSON schemas for key models."""
    output_dir = Path(__file__).parent.parent.parent.parent / "packages" / "spec" / "jsonschema"
    output_dir.mkdir(parents=True, exist_ok=True)

    models = [
        ("chat_request", ChatRequest),
        ("create_strategy_request", CreateStrategyRequest),
        ("strategy_response", StrategyResponse),
        ("preview_request", PreviewRequest),
        ("download_request", DownloadRequest),
    ]

    for name, model in models:
        schema = model.model_json_schema()
        output_file = output_dir / f"{name}.schema.json"
        with open(output_file, "w") as f:
            json.dump(schema, f, indent=2)
        print(f"Generated: {output_file}")


if __name__ == "__main__":
    main()

