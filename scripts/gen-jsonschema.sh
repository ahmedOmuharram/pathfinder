#!/bin/bash
# Generate JSON Schema from Pydantic models (optional)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "JSON Schema generation from Pydantic models..."
echo "This is handled automatically by Pydantic's .model_json_schema() method."
echo ""
echo "To generate schemas manually, run:"
echo ""
echo "  cd $ROOT_DIR/apps/api"
echo "  uv run python scripts/codegen_models.py"

