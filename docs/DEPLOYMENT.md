# Deployment and public demo

How to put the planner online for a demo, and what is and isn't production-grade yet.

## Public HTTPS demo (one command)

```bash
cp .env.example .env        # first time only, then set JWT_SECRET and FERNET_KEY (see comments)
# optional, for AI suggestions: add GROQ_API_KEY=... to .env, or save a model in Model settings
make demo                   # = deploy/public-demo.sh
```

What it does:

1. Starts the Docker Compose stack: Postgres, Redis, RabbitMQ, MinIO, API, worker, beat, and the web app. The web app is the production build served by `vite preview`, which proxies `/api` to the API, so the browser talks to one origin.
2. Waits until the API and the web app answer.
3. Opens a **Cloudflare quick tunnel**: a temporary public `https://<random>.trycloudflare.com` address that forwards to `localhost:5173`. No Cloudflare account is needed, and TLS ends at Cloudflare.

The URL is printed in the terminal. It lasts as long as that terminal runs. Press Ctrl-C to close the tunnel; the stack keeps running until you run `make down`.

Demo sign-in:

| Role | Email | Password |
|---|---|---|
| Data Engineer (runs the flow) | `engineer@example.com` | `Engineer123!` |
| Administrator (model settings, users, audit) | `admin@example.com` | `Admin123456!` |

These are demo users seeded by `backend/scripts/seed_demo.py`. Change or remove them before any real data is uploaded.

### Verified on 2026-10-01

Over the public HTTPS URL, `frontend/scripts/live-walkthrough.mjs` signed in, uploaded the reference file, generated, approved and ran the plan, exported XLSX, CSV and Pipeline, and rolled back to v0. Screenshots are in `docs/benchmarks/public-demo-2026-10-01/`.

The real AI model (Groq `gpt-oss-120b`) ran inside the stack. It proposed two extra steps; both failed validation and were left out, with the reasons shown on the plan (Level 3 B4).

## Limits of this setup

- **It runs on the presenter's machine.** On an old laptop (i3, 8 GB RAM), keep the demo to the reference file or files of a few thousand rows. The 30k-row file works but takes about 3–5 minutes (see [BENCHMARKS.md](BENCHMARKS.md)).
- **Groq free tier:** 8,000 tokens per minute. One AI call is about 3,400 tokens, so run about one dataset per minute. Throttling waits and retries once; past that, the page shows "AI suggestions unavailable" and the deterministic plan still works.
- **The quick-tunnel URL changes on every start** and has no uptime guarantee. For a fixed address, use a named Cloudflare tunnel (needs a free account and a domain).

## Cloud VM with automatic deploys (Level 3 M5)

Every push to `main` that passes all CI checks deploys itself. The `deploy` job in `.github/workflows/ci.yml` copies `deploy/remote-deploy.sh` to the VM and runs it. The script:

1. checks out that commit;
2. starts the API, worker and scheduler from the CI-built, scanned image `ghcr.io/dsribalaji/png6-planner:<sha>`, builds the web app from the same commit, and puts **Caddy** in front (a web server that gets and renews the HTTPS certificate by itself);
3. runs a smoke test: health check, then the reference file end to end (upload, plan, approve, validated export);
4. if the smoke test fails, rolls back to the previously deployed commit and marks the run failed.

The job stays off until you add a VM.

**What you need to provide (one time):**

1. **A Linux VM** with at least 2 vCPU and 4 GB RAM (8 GB if you also run Keycloak), Docker with the compose plugin, and ports 80 and 443 open. **Turn on disk encryption** when you create it (see "Encryption at rest").
2. **A domain name** with a DNS `A` record pointing at the VM's public IP, e.g. `planner.example.com`.
3. **On the VM**, as the deploy user:
   ```bash
   git clone https://github.com/dsribalaji/png6-data-cleaning.git ~/png6-data-cleaning
   cd ~/png6-data-cleaning && cp .env.example .env
   # edit .env: JWT_SECRET, FERNET_KEY, POSTGRES/MinIO passwords, GROQ_API_KEY (optional),
   # and add DOMAIN=planner.example.com
   # behind Caddy, set RATE_LIMIT_CLIENT_HEADER=x-forwarded-for
   ```
4. **In GitHub** (Settings → Secrets and variables → Actions):
   - variables `DEPLOY_HOST` (the VM's address) and `DEPLOY_USER`;
   - secret `DEPLOY_SSH_KEY` (a private key whose public half is in the VM user's `~/.ssh/authorized_keys`);
   - optional secret `DEPLOY_KNOWN_HOSTS` (the VM's host key, from `ssh-keyscan <host>`); without it the first connection trusts whatever key the VM presents.

The next green push to `main` deploys to `https://<DOMAIN>`. To deploy a specific commit by hand (for example after a failed run), run `bash deploy/remote-deploy.sh <sha>` on the VM.

Production settings (`deploy/docker-compose.prod.yml`): only Caddy publishes ports; Postgres, Redis, RabbitMQ and MinIO are reachable only inside the Docker network; Prometheus and Grafana start only with `--profile monitoring`.

## SSO + MFA with Keycloak (Level 3 D-2)

Keycloak is an open-source identity server. With it, people sign in once (SSO) and must also enter a 6-digit code from an authenticator app (MFA; for example Google Authenticator, Microsoft Authenticator or FreeOTP).

```bash
export KEYCLOAK_ADMIN_PASSWORD=<choose one>          # Keycloak's own admin console
# in .env:  AUTH_MODE=oidc   (OIDC_ISSUER / OIDC_JWKS_URL defaults fit this compose stack)
export VITE_AUTH_MODE=oidc                           # build the web app for SSO
docker compose -f deploy/docker-compose.yml --profile sso up -d --build
```

- Keycloak runs on http://localhost:8080 and imports `deploy/keycloak/realm-png6.json`: realm `png6`, web client `png6-web` (authorization code + PKCE), the four app roles, and demo users `engineer`, `admin`, `auditor` and `viewer` (passwords as in the realm file).
- **Demo of MFA:** open the app, then "Sign in with SSO", and sign in as `engineer`. Keycloak shows a QR code; scan it with an authenticator app and enter the code. Every later sign-in asks for a fresh code. The role in Keycloak decides what the user can do in the app.
- In this mode the API accepts only tokens issued by Keycloak, and refuses password sign-in (`403 SSO_REQUIRED`), so nothing bypasses MFA.
- For a public domain: add `https://<DOMAIN>/*` to the `png6-web` client's redirect URIs in the Keycloak admin console, set `KEYCLOAK_PUBLIC_URL`, `OIDC_ISSUER` and `VITE_OIDC_ISSUER` to the public Keycloak address, and run Keycloak in production mode (`start` with a database) rather than `start-dev`.
- **What CI proves** (job `sso`, `backend/scripts/sso_smoke.py`): tokens issued by the realm are accepted, roles are enforced, password sign-in is refused, tampered tokens are rejected, and a demo user cannot get a token before setting up MFA. Scanning a QR code with a phone cannot be automated; that part is the manual demo above.

## Secrets in OpenBao (Level 3 D-4)

OpenBao is the open-source fork of HashiCorp Vault, a secret store. With `--profile secrets`, Compose starts it in dev mode (in memory). Store the secrets once:

```bash
docker compose -f deploy/docker-compose.yml --profile secrets up -d openbao
docker compose -f deploy/docker-compose.yml exec openbao sh -c \
  'BAO_ADDR=http://127.0.0.1:8200 BAO_TOKEN=dev-only-root-token bao kv put secret/png6 JWT_SECRET=... FERNET_KEY=... GROQ_API_KEY=...'
```

Then set `BAO_ADDR=http://openbao:8200` and `BAO_TOKEN=...` in `.env` and remove those secrets from `.env`. The app loads them at startup (`backend/src/planner/core/secrets.py`) and refuses to start if OpenBao is configured but cannot be read. Dev mode loses its data on restart; production needs persistent storage, unseal keys and a token limited to `secret/data/png6`.

## Encryption at rest (Level 3 D-6)

- **Disk:** create the VM with an encrypted disk. Most clouds offer it at creation time (encrypted block volume / default disk encryption), or use LUKS on your own server. All Docker volumes (Postgres, MinIO, Redis, RabbitMQ, uploads) live on that disk.
- **Object storage:** to also encrypt files inside MinIO, set `MINIO_KMS_SECRET_KEY` (format `<key-name>:<base64 32-byte key>`) on the `minio` service and turn on bucket encryption with `mc encrypt set sse-s3 <alias>/planner`. Keep that key in OpenBao, not in `.env`.
- **Model API keys** saved in Model settings are always encrypted in the database (Fernet, `FERNET_KEY`).

## Status against the Level 3 plan

| Item | Status |
|---|---|
| SSO + MFA (Keycloak) | Built (`AUTH_MODE=oidc`); token acceptance, roles and the MFA requirement are verified by the CI `sso` job; the QR-code step is a manual demo |
| Secrets in OpenBao | Built (`--profile secrets`, loader unit-tested); dev mode only |
| Rate limiting, threat model | Built; see `docs/architecture/threat-model.md` |
| Cloud VM, HTTPS (Caddy), automatic deploy with rollback | Written and the compose files validated in CI; **runs only after you add the VM and the GitHub secrets above** |
| Encryption at rest | Documented above; it is a setting on your VM and MinIO, not code |
