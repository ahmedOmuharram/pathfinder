#!/bin/bash
# Generate TypeScript types from OpenAPI spec

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

SPEC_FILE="$ROOT_DIR/packages/spec/openapi.yaml"
OUTPUT_FILE="$ROOT_DIR/apps/web/src/lib/api/generated.ts"

echo "Generating TypeScript types from OpenAPI spec..."

# Check if openapi-typescript is installed
if ! command -v npx &> /dev/null; then
    echo "Error: npx not found. Please install Node.js"
    exit 1
fi

# Generate types
npx openapi-typescript "$SPEC_FILE" -o "$OUTPUT_FILE"

echo "Generated: $OUTPUT_FILE"

