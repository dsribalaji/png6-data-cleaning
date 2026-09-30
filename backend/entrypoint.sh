#!/bin/sh
# One Docker image starts as API, worker, or scheduler.
set -e

case "${MODE:-api}" in
  api)
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000
    ;;
  worker)
    exec celery -A app.workers.celery_app.celery_app worker
    ;;
  scheduler)
    exec celery -A app.workers.celery_app.celery_app beat
    ;;
  *)
    echo "Unknown MODE: ${MODE}. Expected 'api', 'worker', or 'scheduler'." >&2
    exit 1
    ;;
esac
