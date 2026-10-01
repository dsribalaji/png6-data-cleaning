# One image starts as api, worker, or beat (Backend.md).
# The process is chosen by the compose service's `command:` override.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1

WORKDIR /app

# OS security fixes the base image has not picked up yet (CI trivy scan gates HIGH/CRITICAL).
RUN apt-get update && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# uv for installs (Backend.md); falls back to pip if uv is unavailable.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml ./
# --compile-bytecode: PYTHONDONTWRITEBYTECODE=1 stops runtime .pyc caching, so without
# precompiled bytecode every process recompiles litellm & co. on import (~70 s cold).
RUN uv pip install --system --no-cache --compile-bytecode -e . || pip install --no-cache-dir -e .

COPY src/ ./src/
COPY migrations/ ./migrations/
COPY alembic.ini ./
COPY scripts/ ./scripts/
RUN python -m compileall -q src

EXPOSE 8000

# Default: API behind Gunicorn (Backend.md). Compose overrides for worker/beat.
CMD ["gunicorn", "planner.main:app", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
