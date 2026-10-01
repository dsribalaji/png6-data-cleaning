"""D-4: secrets come from OpenBao when it is configured, and startup fails closed."""

from __future__ import annotations

import io
import json

import pytest

from planner.core import secrets


def test_no_bao_addr__nothing_loaded() -> None:
    env: dict[str, str] = {"JWT_SECRET": "from-env"}
    assert secrets.load_openbao_secrets(env) == []
    assert env == {"JWT_SECRET": "from-env"}


def test_bao_configured__kv_v2_keys_override_env(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = {}

    def fake_urlopen(request, timeout):  # type: ignore[no-untyped-def]
        seen["url"], seen["token"] = request.full_url, request.get_header("X-vault-token")
        payload = {"data": {"data": {"JWT_SECRET": "b" * 40, "GROQ_API_KEY": "gsk_x", "n": 1}}}
        return io.BytesIO(json.dumps(payload).encode())

    monkeypatch.setattr(secrets.urllib.request, "urlopen", fake_urlopen)
    env = {"BAO_ADDR": "http://bao:8200/", "BAO_TOKEN": "t", "JWT_SECRET": "old"}
    assert sorted(secrets.load_openbao_secrets(env)) == ["GROQ_API_KEY", "JWT_SECRET"]
    assert env["JWT_SECRET"] == "b" * 40
    assert seen == {"url": "http://bao:8200/v1/secret/data/png6", "token": "t"}


def test_bao_unreachable__startup_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(request, timeout):  # type: ignore[no-untyped-def]
        raise OSError("connection refused")

    monkeypatch.setattr(secrets.urllib.request, "urlopen", boom)
    with pytest.raises(RuntimeError, match="could not be read"):
        secrets.load_openbao_secrets({"BAO_ADDR": "http://bao:8200", "BAO_TOKEN": "t"})


def test_bao_addr_must_be_http() -> None:
    with pytest.raises(RuntimeError, match="http"):
        secrets.load_openbao_secrets({"BAO_ADDR": "file:///etc/passwd", "BAO_TOKEN": "t"})
