## Pathfinder API (`apps/api`)

FastAPI backend for PathFinder. It exposes a streaming chat API (SSE) that runs a unified **tool-calling agent**, persists conversations/strategies, and integrates with **VEuPathDB/WDK** plus optional **Qdrant RAG**.

### Key entrypoints

- **App**: `src/veupath_chatbot/main.py`
- **Chat SSE endpoint**: `src/veupath_chatbot/transport/http/routers/chat.py` (`POST /api/v1/chat`)
- **Chat orchestration**: `src/veupath_chatbot/services/chat/orchestrator.py`
- **Streaming implementation**: `src/veupath_chatbot/transport/http/streaming.py`
- **Unified agent**: `src/veupath_chatbot/ai/agents/executor.py` (`PathfinderAgent`)
- **Agent factory**: `src/veupath_chatbot/ai/agents/factory.py`

### Package structure

```
src/veupath_chatbot/
  ai/                        # Agent construction and orchestration
    agents/                  #   Unified PathfinderAgent, subtask agent, experiment agent, factory
    models/                  #   Model catalog: provider mappings, reasoning config
    orchestration/           #   Sub-agent delegation, scheduler, subkani orchestrator
      subkani/               #     SubKani multi-agent coordination
    prompts/                 #   System prompt templates and loader
    stubs/                   #   Type stubs for downstream extensions
    tools/                   #   All agent tools (unified -- no mode split)
      planner/               #     Artifact, experiment, gene, optimization tools
      strategy_tools/        #     Strategy graph mutation tools (step_ops, graph_ops, etc.)
      unified_registry.py    #     Unified tool registry mixin
      catalog_tools.py       #     Catalog browsing tools
      catalog_rag_tools.py   #     RAG-backed catalog search
      conversation_tools.py  #     Conversation management tools
      execution_tools.py     #     Strategy execution tools
      result_tools.py        #     Result retrieval tools
      research_registry.py   #     Research/literature tool registry
      strategy_registry.py   #     Strategy tool registry
      registry.py            #     Base tool registry
  domain/                    # Core business logic (no I/O)
    parameters/              #   Parameter decoding, validation, vocabulary resolution
    research/                #   Citation extraction and research helpers
    strategy/                #   Strategy compilation, explanation, metadata, session
      validate/              #     Plan validation against WDK constraints
  integrations/              # External service clients
    embeddings/              #   OpenAI embedding client
    vectorstore/             #   Qdrant wrapper, collections, ingestion pipeline
      ingest/                #     WDK catalog + public strategy ingestion
    veupathdb/               #   WDK HTTP client (cookie-based auth)
      strategy_api/          #     Strategy CRUD, steps, reports, helpers
  jobs/                      # Background tasks (startup ingestion)
  persistence/               # Database layer
    repositories/            #   SQLAlchemy repositories (strategies, sessions, experiments)
  platform/                  # Shared infrastructure
    config.py                #   Settings (API keys, DB URL, feature flags)
    context.py               #   Request-scoped context variables
    errors.py                #   Error codes and exception types
    logging.py               #   Structured logging setup
    security.py              #   Auth and authorization helpers
    types.py                 #   JSONObject, JSONArray, JSONValue aliases
  services/                  # Application services
    catalog/                 #   Catalog browsing, search spec loading, parameter helpers
      parameters/            #     Parameter-specific catalog logic
    chat/                    #   Chat orchestration and message processing
      orchestrator.py        #     SSE stream entry point, agent construction
      processor.py           #     Stream processing, event handling
      bootstrap.py           #     Strategy/history initialization
      events.py              #     Chat event types
      event_handlers.py      #     Event dispatch logic
      finalization.py        #     Post-stream cleanup
      mention_context.py     #     @mention context injection
      message_builder.py     #     Message construction helpers
      thinking.py            #     Thinking/reasoning display
    experiment/              #   Experiment mode (comparison, evaluation, enrichment)
      core/                  #     Experiment config, streaming
      seed/                  #     Experiment seeding data
      step_analysis/         #     Per-step analysis utilities
      types/                 #     Experiment Pydantic models
    gene_lookup/             #   Gene ID resolution
    parameter_optimization/  #   Parameter tuning via optimization loops
    research/                #   Research paper retrieval
      clients/               #     External research API clients
    strategies/              #   Strategy lifecycle
      engine/                #     Graph integrity, step ordering, execution helpers
  transport/                 # HTTP layer
    http/
      routers/               #   FastAPI routers (chat, strategies, experiments, sites, etc.)
        experiments/          #     CRUD, execution, evaluation, analysis, comparison, etc.
        strategies/           #     CRUD, plan, counts, WDK import
        steps/                #     Step-level endpoints
        sites/                #     Site-scoped catalog, gene, parameter endpoints
      schemas/               #   Pydantic request/response DTOs
      deps.py                #   FastAPI dependencies (auth, DB, site context)
      streaming.py           #   SSE event formatting and stream lifecycle
      sse.py                 #   Low-level SSE encoding helpers
  tests/                     # Test suite
    fixtures/                #   Shared test fixtures and WDK mock data
    integration/             #   Integration tests
    unit/                    #   Unit tests
  devtools/                  # Developer utilities (OpenAPI generation, etc.)
```

### Architecture overview

**Request flow** (chat):

1. `POST /api/v1/chat` arrives at `transport/http/routers/chat.py`
2. FastAPI dependencies (`deps.py`) inject auth context, DB session, site context
3. `services/chat/orchestrator` bootstraps the conversation (strategy, history) and creates the agent
4. The orchestrator builds a single unified `PathfinderAgent` (`ai/agents/factory.py`) with:
   - The selected LLM engine (OpenAI, Anthropic, Google)
   - The full tool suite from `ai/tools/` (via `UnifiedToolRegistryMixin`)
   - System prompts from `ai/prompts/`
5. The agent streams responses as SSE events via `transport/http/streaming.py`
6. Tool calls mutate strategy state via `services/strategies/` and are synced to WDK

**Unified agent**:

There is a single `PathfinderAgent` that has access to all tools -- strategy construction, catalog browsing, RAG retrieval, gene lookup, research, artifacts, and more. The model decides autonomously when to research vs. execute, with no separate plan/execute mode selection. Complex goals can still be decomposed into sub-tasks via the `ai/orchestration/` layer, which coordinates multiple sub-agents (SubKani) to build multi-step strategies.

**Persistence**:

- PostgreSQL via SQLAlchemy async sessions
- Repositories in `persistence/repositories/` for strategies, sessions, experiments
- Schema created via `create_all` (no Alembic migrations yet)

**VEuPathDB integration**:

- `integrations/veupathdb/` wraps the WDK REST API with cookie-based auth
- Strategy API client handles CRUD, step management, and result reports
- Auto-push (`services/strategies/auto_push.py`) syncs local strategy state back to WDK

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
