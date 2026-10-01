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

## Still open for production (Level 3 plan, M4–M5)

| Item | Status |
|---|---|
| SSO + MFA (Keycloak) | not started; sign-in is JWT + Argon2 with role checks on every route |
| Secrets in OpenBao | not started; secrets live in `.env` (git-ignored) |
| Cloud VM, encrypted disk, automatic deploy from CI | not started; CI builds, scans and publishes the image to `ghcr.io/dsribalaji/png6-planner:<sha>`, but nothing deploys it yet |
