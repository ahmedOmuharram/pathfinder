FROM python:3.14-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# ── Cached layer: dependencies + model (busted only by pyproject.toml/uv.lock) ──

# Copy dependency manifests only — NOT application source code.
COPY apps/api/pyproject.toml apps/api/
COPY apps/api/uv.lock apps/api/
COPY apps/api/config.toml apps/api/
COPY packages/shared-py/pyproject.toml packages/shared-py/
COPY packages/shared-py/src packages/shared-py/src

# Install dependencies without the project itself (no source code needed).
# Cache mount preserves uv's download cache across builds — even when deps
# change, already-fetched packages aren't re-downloaded from PyPI.
WORKDIR /app/apps/api
RUN --mount=type=cache,target=/root/.cache/uv \
    UV_LINK_MODE=copy uv sync --frozen --no-install-project

# Pre-download the sentence-transformer model into the image so startup
# doesn't depend on HuggingFace availability or rate limits.
# Lives in the same cached layer group as deps — code changes don't bust this.
RUN .venv/bin/python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('nomic-ai/nomic-embed-text-v1.5', trust_remote_code=True)"

# Prevent HuggingFace from phoning home at runtime — the model is cached.
ENV HF_HUB_OFFLINE=1

# ── Fast layer: application code (re-runs on every code change, but cheap) ──

WORKDIR /app

# Copy Alembic config and migrations
COPY apps/api/alembic.ini apps/api/
COPY apps/api/alembic apps/api/alembic

# Copy application code
COPY apps/api/src apps/api/src

# Copy optional Ollama models config (glob avoids failure if missing)
COPY ollama_models.yam[l] ./

# Install the project package (deps already installed — just links the source).
WORKDIR /app/apps/api
RUN uv sync --frozen

# Expose port
EXPOSE 8000

# Health check — use /health/ready (checks DB) so Docker waits for full readiness.
# start-period covers warm-up: model loading + catalog preload for all 14 sites.
HEALTHCHECK --interval=10s --timeout=10s --start-period=300s --retries=5 \
    CMD curl -f http://localhost:8000/health/ready || exit 1

# Run the application
CMD ["uv", "run", "uvicorn", "veupath_chatbot.main:app", "--host", "0.0.0.0", "--port", "8000"]
