"""Load secrets from OpenBao before settings are read (Level 3 D-4, NFR-01).

OpenBao is the open-source fork of HashiCorp Vault. When BAO_ADDR and BAO_TOKEN
are set, every key stored at the KV v2 path BAO_SECRET_PATH (default
"secret/data/png6") is copied into the process environment, where Settings and
the LLM gateway pick it up: JWT_SECRET, FERNET_KEY, DATABASE_URL, GROQ_API_KEY.
Without BAO_ADDR nothing changes and secrets come from env / .env as before.

Fails closed: if OpenBao is configured but cannot be read, startup stops rather
than running on missing or stale secrets.
"""

from __future__ import annotations

import json
import os
import urllib.request


def load_openbao_secrets(environ: dict[str, str] = os.environ) -> list[str]:  # type: ignore[assignment]
    """Copy the OpenBao secret's keys into `environ`; returns the key names loaded."""
    addr, token = environ.get("BAO_ADDR"), environ.get("BAO_TOKEN")
    if not addr or not token:
        return []
    path = environ.get("BAO_SECRET_PATH", "secret/data/png6").strip("/")
    request = urllib.request.Request(
        f"{addr.rstrip('/')}/v1/{path}", headers={"X-Vault-Token": token}
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310 (operator-set URL)
            body = json.load(response)
    except Exception as exc:
        raise RuntimeError(f"OpenBao is configured (BAO_ADDR) but {path} could not be read: {exc}") from exc
    data = body.get("data", {}).get("data", {})
    loaded = [k for k, v in data.items() if isinstance(v, str)]
    for key in loaded:
        environ[key] = data[key]
    return loaded
