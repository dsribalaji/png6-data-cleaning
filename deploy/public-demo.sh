#!/usr/bin/env bash
# Public HTTPS demo: start the Docker Compose stack and expose the web app through a
# Cloudflare quick tunnel (no account, temporary *.trycloudflare.com URL).
# Usage: deploy/public-demo.sh        Stop: Ctrl-C (the stack keeps running; `make down`).
set -euo pipefail
cd "$(dirname "$0")/.."

docker compose -f deploy/docker-compose.yml up -d --build \
  postgres redis rabbitmq minio api worker beat frontend
echo "waiting for the API and the web app..."
timeout 600 bash -c 'until curl -sf localhost:8000/api/v1/health/live >/dev/null; do sleep 3; done'
timeout 300 bash -c 'until curl -sf -o /dev/null localhost:5173; do sleep 3; done'

echo "starting the tunnel; the public https URL is printed below (…trycloudflare.com)"
exec cloudflared tunnel --no-autoupdate --url http://localhost:5173
