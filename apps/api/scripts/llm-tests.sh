#!/usr/bin/env bash
# Run the per-phase LLM tests (real OpenAI + real WDK).
# Default pytest does NOT collect these — invoke through this script.
#
# Picks OPENAI_API_KEY from one of (in order): env, ../../.env.dev.
# Docker-only endpoints (langfuse, worker db) are unset in the conftest,
# so the tests work from the host.
#
# Usage:
#   scripts/llm-tests.sh                  # all llm tests
#   scripts/llm-tests.sh -k planning      # filter by name
#   scripts/llm-tests.sh -x                # stop on first failure
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  ENV_FILE="../../.env.dev"
  if [[ -f "$ENV_FILE" ]]; then
    line="$(grep -E '^OPENAI_API_KEY=' "$ENV_FILE" || true)"
    if [[ -n "$line" ]]; then
      export OPENAI_API_KEY="${line#OPENAI_API_KEY=}"
    fi
  fi
fi

if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "error: OPENAI_API_KEY not set and no OPENAI_API_KEY= line in $ENV_FILE" >&2
  exit 1
fi

exec uv run pytest \
  src/pathfinder/tests/llm \
  -m llm \
  --override-ini "addopts=" \
  -v \
  "$@"
