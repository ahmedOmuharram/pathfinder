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

# Copy application code (needed because `uv sync` installs the project)
COPY apps/api/src apps/api/src

# Install dependencies
WORKDIR /app/apps/api
RUN uv sync --frozen

WORKDIR /app/apps/api

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["uv", "run", "uvicorn", "veupath_chatbot.main:app", "--host", "0.0.0.0", "--port", "8000"]

