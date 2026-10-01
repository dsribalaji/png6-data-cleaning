#!/usr/bin/env bash
# Runs ON the cloud VM, called by the CI `deploy` job over SSH (Level 3 E5):
#   deploy/remote-deploy.sh <git-sha>
# Needs: the repo cloned at $APP_DIR, a filled-in .env next to it, DOMAIN in .env,
# and Docker logged in to ghcr.io (the CI job does that with a short-lived token).
#
# 1. checks out <git-sha> and starts that version (api/worker/beat image from GHCR,
#    web app built from the same commit, Caddy for HTTPS); migrations run on api start;
# 2. smoke test: health, sign-in, and the reference file end to end (upload -> plan ->
#    approve -> validated export) through scripts/benchmark.py inside the api container;
# 3. on any failure, rolls back to the previously deployed commit and exits non-zero.
set -euo pipefail

SHA="${1:?usage: remote-deploy.sh <git-sha>}"
APP_DIR="${APP_DIR:-$HOME/png6-data-cleaning}"
cd "$APP_DIR"
PREV="$(cat .deployed_sha 2>/dev/null || true)"
DOMAIN="$(grep -E '^DOMAIN=' .env | cut -d= -f2-)"
export DOMAIN

compose() {
  docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml \
    --profile prod "$@"
}

# Steps are chained with && on purpose: bash ignores `set -e` inside functions called
# from an `if`, so each step's failure must stop the function explicitly.
start() {
  git fetch --quiet origin &&
    git checkout --quiet --detach "$1" &&
    export IMAGE_TAG="$1" &&
    compose pull api worker beat &&
    compose up -d --build --remove-orphans
}

smoke() {
  timeout 300 bash -c "until curl -sf https://$DOMAIN/api/v1/health/live >/dev/null; do sleep 5; done" ||
    return 1
  if grep -qE '^AUTH_MODE=oidc' .env; then
    # Under SSO the API refuses password sign-in, so the scripted end-to-end run cannot
    # sign in; check the realm is reachable instead (the CI `sso` job covers the flow).
    issuer="$(grep -E '^OIDC_ISSUER=' .env | cut -d= -f2-)"
    curl -sf "$issuer/.well-known/openid-configuration" >/dev/null
    return
  fi
  compose cp data/reference/VendorInvoices_uncleaned.xlsx api:/tmp/reference.xlsx &&
    compose exec -T api python scripts/benchmark.py /tmp/reference.xlsx --base http://localhost:8000
}

echo "deploying $SHA (previous: ${PREV:-none})"
if start "$SHA" && smoke; then
  echo "$SHA" > .deployed_sha
  echo "deployed $SHA to https://$DOMAIN"
  exit 0
fi

echo "smoke test failed for $SHA" >&2
if [ -n "$PREV" ]; then
  echo "rolling back to $PREV" >&2
  start "$PREV" && smoke && echo "rolled back to $PREV" >&2
fi
exit 1
