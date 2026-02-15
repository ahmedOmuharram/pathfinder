## Pathfinder API (`apps/api`)

FastAPI backend for PathFinder. It exposes a streaming chat API (SSE) that runs the **planner** and **executor** tool-calling agents, persists sessions/strategies, and integrates with **VEuPathDB/WDK** plus optional **Qdrant RAG**.

### Key entrypoints

- **App**: `src/veupath_chatbot/main.py`
- **Chat SSE endpoint**: `src/veupath_chatbot/transport/http/routers/chat.py` (`POST /api/v1/chat`)
- **Chat orchestration**: `src/veupath_chatbot/services/chat/orchestrator.py`
- **Streaming implementation**: `src/veupath_chatbot/transport/http/streaming.py`
- **Executor agent runtime**: `src/veupath_chatbot/ai/agent_runtime.py`
- **Planner agent runtime**: `src/veupath_chatbot/ai/planner_runtime.py`

### Configuration

Settings are loaded from:

- **TOML**: `config.toml` (checked in; this file is expected at `apps/api/config.toml`)
- **Environment**: `.env` (not checked in; see `.env.example`)

Common env vars:

- `OPENAI_API_KEY` (or `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` if using those providers)
- `API_SECRET_KEY` (32+ chars)
- `DATABASE_URL` (defaults to PostgreSQL on `localhost:5432` if unset)
- `DEFAULT_MODEL_ID`, `DEFAULT_REASONING_EFFORT` (optional; defaults are `openai/gpt-5` and `medium`)
- `QDRANT_URL`, `QDRANT_API_KEY` (optional; compose sets container-friendly defaults)
- Startup-ingestion tuning lives in `config.toml` (keys: `rag_startup_*`)

### Run locally (no Docker)

Start local dependencies (recommended):

```bash
docker compose up -d db qdrant
```

```bash
cd apps/api
uv sync --extra dev
uv run uvicorn veupath_chatbot.main:app --reload --host 0.0.0.0 --port 8000
```

API will be available at:

- `http://localhost:8000/health`
- `http://localhost:8000/docs` (when docs are enabled)

### Build Sphinx docs

```bash
cd apps/api
uv sync --extra dev
uv run sphinx-build -b html docs docs/_build/html
```

Output: `docs/_build/html/`. Hosted at [veupathdb-pathfinder.readthedocs.io](https://veupathdb-pathfinder.readthedocs.io/).

### Run tests / lint / typecheck

```bash
cd apps/api
uv run pytest
uv run ruff check .
uv run mypy src
```

### Persistence & migrations (current state)

- Uses SQLAlchemy async sessions (`src/veupath_chatbot/persistence/session.py`).
- Dev defaults to **PostgreSQL** (to match Docker/production).
- There is **no Alembic migrations workflow yet**; schema is created via `create_all`.

### RAG / Qdrant

RAG retrieval is implemented (catalog + example plans). When `rag_enabled=true` (default; configured in `config.toml`),
the API starts incremental ingestion in the background on startup **if `OPENAI_API_KEY` is set**.

To force a full reset + rebuild via Docker Compose:

```bash
docker compose --profile ingest run --rm rag_reindex
```

Notes:

- Startup ingestion requires **`OPENAI_API_KEY`** (embeddings). If missing, the API will run but RAG will stay empty.
- Manual reindex writes a JSONL report under `apps/api/ingest_reports/` (gitignored).

