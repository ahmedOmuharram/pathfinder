# Development Guide

This document covers the full quality toolchain: local hooks, CI pipelines, security scanning, static analysis, and architectural enforcement.

## Pre-commit hooks

Install hooks once after cloning:

```bash
cd apps/api
uv sync --extra dev
cd ../..
yarn install
uv run pre-commit install --hook-type pre-commit --hook-type pre-push
```

### On every commit (pre-commit)

| Hook | Scope | What it does |
|------|-------|--------------|
| **ruff check** | `apps/api/` | Lint Python (with `--fix`) |
| **ruff format** | `apps/api/` | Format Python |
| **mypy** | `apps/api/` | Strict type checking |
| **openapi spec regen** | `apps/api/` | Regenerate `openapi.json` if API code changed |
| **file size check** | `apps/api/src/` | Fail if any Python file exceeds 300 LOC (excluding blanks/comments/tests) |
| **import-linter** | `apps/api/` | Enforce backend layer contracts (transport → services → domain) |
| **prettier** | `apps/web/`, `packages/shared-ts/` | Format TypeScript/CSS/JSON |
| **eslint** | `apps/web/`, `packages/shared-ts/` | Lint TypeScript |
| **tsc --noEmit** | `apps/web/`, `packages/shared-ts/` | Type check frontend |
| **check boundaries** | `apps/web/`, `packages/shared-ts/` | Enforce feature isolation (no cross-feature imports) |
| **openapi types regen** | `packages/shared-ts/`, `apps/api/` | Regenerate TypeScript types from OpenAPI spec |

### On push (pre-push)

| Hook | Scope | What it does |
|------|-------|--------------|
| **pytest** | `apps/api/` | Run API unit tests |
| **vitest** | `apps/web/`, `packages/shared-ts/` | Run frontend unit tests |
| **next build** | `apps/web/`, `packages/shared-ts/` | Full production build |
| **pip-audit** | `apps/api/pyproject.toml` | Check Python dependencies for known vulnerabilities |
| **knip** | `apps/web/`, `packages/shared-ts/` | Detect unused exports, dependencies, and files |

## Testing

### API (Python)

```bash
cd apps/api

# Unit tests
uv run pytest src/veupath_chatbot/tests/unit/ -v

# All tests (unit + integration)
uv run pytest src/veupath_chatbot/tests/ -v

# With coverage
uv run pytest --cov=src/veupath_chatbot --cov-report=term-missing

# Coverage as XML (for CI / SonarQube)
uv run pytest --cov=src --cov-report=xml
```

### Web (TypeScript)

```bash
cd apps/web

# Unit / integration tests
npx vitest run

# With coverage
yarn test:coverage

# E2E (requires API + web running)
npx playwright test
```

### Docker

```bash
# Run API tests inside the container
docker compose exec api uv run pytest src/veupath_chatbot/tests/ -v
```

## Linting and type checking

### API

```bash
cd apps/api

uv run ruff check src/                   # Lint
uv run ruff format --check src/          # Format check (no changes)
uv run mypy --strict src/veupath_chatbot/ # Type check
```

### Web

```bash
cd apps/web

npx eslint src/                    # Lint
yarn format:check                  # Prettier check (no changes)
npx tsc --noEmit                   # Type check
node scripts/check-boundaries.mjs  # Feature isolation
```

## Architectural enforcement

Three mechanisms enforce code structure beyond standard linting:

### File size cap

`scripts/check-file-size.sh` fails if any Python source file in `apps/api/src/` exceeds **300 lines** of code (excluding blanks, comments, tests, seeds, and prompt files). This prevents modules from growing too large.

```bash
bash scripts/check-file-size.sh apps/api/src 300
```

### Import linter

[import-linter](https://import-linter.readthedocs.io/) enforces backend layer contracts — e.g., transport can call services but not domain directly. Configuration is in `apps/api/pyproject.toml` under `[tool.importlinter]`.

```bash
cd apps/api && uv run lint-imports
```

### Boundary checker

`apps/web/scripts/check-boundaries.mjs` enforces frontend feature isolation: features may not import from other features. Exemptions are configured in the script itself.

```bash
cd apps/web && node scripts/check-boundaries.mjs
```

## CI (GitHub Actions)

The CI workflow (`.github/workflows/ci.yml`) runs on push to `main`/`develop` and on PRs to `main`:

| Job | What it checks |
|-----|----------------|
| **lint-api** | ruff, ruff format, mypy, OpenAPI spec freshness |
| **test-api** | pytest with coverage (Postgres + Qdrant service containers) |
| **lint-web** | eslint, prettier, tsc, boundary check |
| **test-web** | vitest with coverage |
| **check-shared-ts** | OpenAPI-generated types are up to date |
| **test-e2e** | Playwright against real API + web (mock chat provider, Postgres, Qdrant, Redis) |
| **build-docs** | Sphinx docs build |

## Security scanning

The security workflow (`.github/workflows/security.yml`) runs on push/PR to `main` and weekly (Monday 6 AM UTC):

| Job | Tool | What it catches |
|-----|------|-----------------|
| **dependency-scan** | [Trivy](https://trivy.dev/) | Known CVEs in dependencies (CRITICAL + HIGH) |
| **secret-scan** | [TruffleHog](https://trufflesecurity.com/trufflehog) | Verified secrets in git history |
| **codeql** | [CodeQL](https://codeql.github.com/) | Static analysis for Python + JavaScript (injection, XSS, etc.) |

Locally, `pip-audit` runs as a pre-push hook for Python dependency vulnerabilities.

## Code quality analysis (SonarQube)

A local [SonarQube Community](https://www.sonarsource.com/open-source-editions/sonarqube-community-edition/) instance provides static analysis, code smells, duplication detection, and coverage visualization.

### Setup

```bash
# 1. Start SonarQube (runs under the "quality" profile)
docker compose --profile quality up -d

# 2. Wait ~2 min for startup, then log in at http://localhost:9000 (admin / admin)
#    Generate a token: My Account → Security → Generate Token

# 3. Install the CLI scanner
brew install sonar-scanner
```

### Running a scan

```bash
export SONAR_TOKEN=<your-token>

# Generate coverage + scan
./scripts/sonar-scan.sh

# Scan with existing coverage reports (skip tests)
./scripts/sonar-scan.sh --no-test
```

Results: `http://localhost:9000/dashboard?id=pathfinder`

Configuration: `sonar-project.properties` (repo root).
