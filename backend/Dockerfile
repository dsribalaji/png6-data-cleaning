# One image starts as api, worker, or beat (Backend.md).
# The process is chosen by the compose service's `command:` override.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# uv for installs (Backend.md); falls back to pip if uv is unavailable.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml ./
RUN uv pip install --system --no-cache -e . || pip install --no-cache-dir -e .

COPY src/ ./src/
COPY migrations/ ./migrations/
COPY alembic.ini ./

EXPOSE 8000

# Default: API behind Gunicorn (Backend.md). Compose overrides for worker/beat.
CMD ["gunicorn", "planner.main:app", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
