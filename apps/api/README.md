## Pathfinder API (`apps/api`)

FastAPI backend for PathFinder. It exposes a streaming chat API (SSE) that runs a unified **tool-calling agent**, persists conversations/strategies, and integrates with **VEuPathDB/WDK**.

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
    agents/                  #   Unified PathfinderAgent, subtask agent, factory
    models/                  #   Model catalog: provider mappings, reasoning config
    orchestration/           #   Sub-agent delegation, scheduler
      subkani/               #     SubKani multi-agent coordination
    prompts/                 #   System prompt templates and loader
    stubs/                   #   Type stubs for downstream extensions
    tools/                   #   All agent tools (unified -- no mode split)
      planner/               #     Artifact, experiment, gene, optimization, workbench tools
      strategy_tools/        #     Strategy graph mutation tools (step_ops, graph_ops, etc.)
      unified_registry.py    #     Unified tool registry mixin
      catalog_tools.py       #     Catalog browsing tools
      conversation_tools.py  #     Conversation management tools
      execution_tools.py     #     Strategy execution tools
      export_tools.py        #     Data export tools
      result_tools.py        #     Result retrieval tools
      research_registry.py   #     Research/literature tool registry
      strategy_registry.py   #     Strategy tool registry
      registry.py            #     Base tool registry
      wdk_error_handler.py   #     WDK error handling
      workbench_read_tools.py #    Workbench data access tools
  domain/                    # Core business logic (no I/O)
    parameters/              #   Parameter decoding, validation, vocabulary resolution
    research/                #   Citation extraction and research helpers
    strategy/                #   Strategy AST, compilation, explanation, metadata, validation
  integrations/              # External service clients
    veupathdb/               #   WDK HTTP client (cookie-based auth)
      strategy_api/          #     Strategy CRUD, steps, reports, helpers
  jobs/                      # Background tasks (startup ingestion)
  persistence/               # Database layer
    repositories/            #   SQLAlchemy repositories (users, streams, control sets)
  platform/                  # Shared infrastructure
    config.py                #   Settings (API keys, DB URL, feature flags)
    context.py               #   Request-scoped context variables
    errors.py                #   Error codes and exception types
    events.py                #   Event bus for cross-cutting concerns
    health.py                #   Health check logic
    logging.py               #   Structured logging setup
    parsing.py               #   Input parsing utilities
    pydantic_validation.py   #   Pydantic validation helpers
    redis.py                 #   Redis client and connection management
    security.py              #   Auth and authorization helpers
    store.py                 #   Generic store abstractions
    tasks.py                 #   Background task infrastructure
    tool_errors.py           #   Tool-specific error formatting
    types.py                 #   JSONObject, JSONArray, JSONValue aliases
  services/                  # Application services
    catalog/                 #   Catalog browsing, search spec loading, parameter helpers
      parameters/            #     Parameter-specific catalog logic
    chat/                    #   Chat orchestration and message processing
      orchestrator.py        #     SSE stream entry point, agent construction
      streaming.py           #     Stream processing, event handling
      events.py              #     Chat event types
      mention_context.py     #     @mention context injection
      utils.py               #     Shared chat utilities
    experiment/              #   Experiment mode (comparison, evaluation, enrichment)
      core/                  #     Experiment config, streaming
      seed/                  #     Experiment seeding (per-database seed definitions)
      step_analysis/         #     Per-step analysis utilities
      types/                 #     Experiment Pydantic models
    export/                  #   Data export (CSV, TXT)
    gene_lookup/             #   Gene ID resolution
    gene_sets/               #   Gene set management (CRUD, confidence, ensemble)
    parameter_optimization/  #   Parameter tuning via optimization loops
    research/                #   Research paper retrieval
      clients/               #     External research API clients (PubMed, arXiv, etc.)
    strategies/              #   Strategy lifecycle
      engine/                #     Graph integrity, step ordering, execution helpers
    wdk/                     #   WDK integration helpers (enrichment, record types, results)
    workbench_chat/          #   Workbench-specific chat orchestration
  transport/                 # HTTP layer
    http/
      routers/               #   FastAPI routers
        chat.py              #     Chat SSE endpoint
        control_sets.py      #     Control set CRUD
        dev.py               #     Dev login and utilities
        exports.py           #     Data export endpoints
        gene_sets.py         #     Gene set CRUD
        health.py            #     Health/readiness probes
        internal.py          #     Internal admin endpoints
        models.py            #     Model catalog endpoints
        operations.py        #     Long-running operation tracking
        tools.py             #     Tool listing endpoint
        user_data.py         #     User data management
        veupathdb_auth.py    #     VEuPathDB auth proxy
        experiments/          #     Experiment CRUD, execution, evaluation, analysis, etc.
        sites/                #     Site-scoped catalog, gene, parameter endpoints
        strategies/           #     Strategy CRUD, plan, counts, WDK import
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

There is a single `PathfinderAgent` that has access to all tools -- strategy construction, catalog browsing, gene lookup, research, artifacts, and more. The model decides autonomously when to research vs. execute, with no separate plan/execute mode selection. Complex goals can still be decomposed into sub-tasks via the `ai/orchestration/` layer, which coordinates multiple sub-agents (SubKani) to build multi-step strategies.

**Persistence**:

- PostgreSQL via SQLAlchemy async sessions
- Repositories in `persistence/repositories/` for users, streams, control sets
- Uses **Alembic** for schema migrations (see `alembic/versions/`). Initial schema is also bootstrapped via `create_all` for development convenience.

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
- `DEFAULT_MODEL_ID`, `DEFAULT_REASONING_EFFORT` (optional; defaults are `openai/gpt-4.1` and `medium`)
### Run locally (no Docker)

Start local dependencies (recommended):

```bash
docker compose up -d db redis
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
- Uses **Alembic** for schema migrations (see `alembic/versions/`). Initial schema is also bootstrapped via `create_all` for development convenience.

