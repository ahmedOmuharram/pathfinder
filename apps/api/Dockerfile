FROM python:3.14-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Copy dependency files
COPY apps/api/pyproject.toml apps/api/
COPY apps/api/uv.lock apps/api/
COPY apps/api/config.toml apps/api/
COPY packages/shared-py/pyproject.toml packages/shared-py/
COPY packages/shared-py/src packages/shared-py/src

# Copy Alembic config and migrations
COPY apps/api/alembic.ini apps/api/
COPY apps/api/alembic apps/api/alembic

# Copy application code (needed because `uv sync` installs the project)
COPY apps/api/src apps/api/src

# Copy optional Ollama models config (glob avoids failure if missing)
COPY ollama_models.yam[l] ./

# Install dependencies
WORKDIR /app/apps/api
RUN uv sync --frozen

WORKDIR /app/apps/api

# Pre-download the sentence-transformer model into the image so startup
# doesn't depend on HuggingFace availability or rate limits.
RUN uv run python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

# Prevent HuggingFace from phoning home at runtime — the model is cached.
ENV HF_HUB_OFFLINE=1

# Expose port
EXPOSE 8000

# Health check — use /health/ready (checks DB) so Docker waits for full readiness.
# start-period covers warm-up: model loading + catalog preload for all 14 sites.
HEALTHCHECK --interval=10s --timeout=10s --start-period=300s --retries=5 \
    CMD curl -f http://localhost:8000/health/ready || exit 1

# Run the application
CMD ["uv", "run", "uvicorn", "veupath_chatbot.main:app", "--host", "0.0.0.0", "--port", "8000"]

