#!/usr/bin/env bash
# Run SonarQube analysis locally.
#
# Prerequisites:
#   1. SonarQube running: docker compose --profile quality up -d
#   2. sonar-scanner CLI:  brew install sonar-scanner
#   3. SONAR_TOKEN env var (generate at http://localhost:9000 → My Account → Security)
#
# Usage:
#   ./scripts/sonar-scan.sh            # generate coverage + scan
#   ./scripts/sonar-scan.sh --no-test  # skip tests, scan with existing coverage reports
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# ── Check prerequisites ────────────────────────────────────────
if ! command -v sonar-scanner &>/dev/null; then
  echo "Error: sonar-scanner not found. Install with: brew install sonar-scanner" >&2
  exit 1
fi

if [[ -z "${SONAR_TOKEN:-}" ]]; then
  echo "Error: SONAR_TOKEN not set. Generate one at http://localhost:9000 → My Account → Security" >&2
  exit 1
fi

if ! curl -sf http://localhost:9000/api/system/status | grep -q UP; then
  echo "Error: SonarQube not reachable at localhost:9000." >&2
  echo "Start it with: docker compose --profile quality up -d" >&2
  exit 1
fi

# ── Generate coverage reports ──────────────────────────────────
if [[ "${1:-}" != "--no-test" ]]; then
  echo "▸ Running API tests with coverage..."
  (cd apps/api && uv run pytest --cov=src --cov-report=xml -q)

  echo "▸ Running Web tests with coverage..."
  (cd apps/web && yarn test:coverage)
else
  echo "▸ Skipping tests (--no-test)"
fi

# ── Run SonarQube scanner ──────────────────────────────────────
echo "▸ Running SonarQube analysis..."
sonar-scanner -Dsonar.token="$SONAR_TOKEN"

echo "✓ Done. View results at http://localhost:9000/dashboard?id=pathfinder"
