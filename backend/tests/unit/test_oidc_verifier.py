"""D-2: Keycloak tokens are accepted only when signed by the realm and issued by it."""

from __future__ import annotations

import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from planner.core import security
from planner.core.errors import AppError

ISSUER = "http://localhost:8080/realms/png6"
REALM_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _verifier() -> security.KeycloakTokenVerifier:
    v = security.KeycloakTokenVerifier(ISSUER)
    # Stands in for the realm JWKS: always the realm's public key.
    v._jwks = SimpleNamespace(  # type: ignore[assignment]
        get_signing_key_from_jwt=lambda token: SimpleNamespace(key=REALM_KEY.public_key())
    )
    return v


def _token(key=REALM_KEY, iss=ISSUER, roles=("data_engineer",), exp_in=300):  # type: ignore[no-untyped-def]
    claims = {
        "iss": iss,
        "sub": "6f1c2a9e-1b2c-4d5e-8f90-123456789abc",
        "email": "kc@example.com",
        "exp": int(time.time()) + exp_in,
        "realm_access": {"roles": list(roles)},
    }
    return jwt.encode(claims, key, algorithm="RS256")


def test_valid_realm_token__mapped_to_highest_app_role() -> None:
    payload = _verifier().verify(_token(roles=("viewer", "administrator", "offline_access")))
    assert payload["role"] == "administrator" and payload["email"] == "kc@example.com"


@pytest.mark.parametrize(
    "token",
    [
        _token(key=OTHER_KEY),  # not signed by the realm
        _token(iss="http://evil/realms/png6"),  # another issuer
        _token(exp_in=-10),  # expired
        jwt.encode({"sub": "x", "role": "administrator"}, "a" * 40, algorithm="HS256"),  # local JWT
    ],
)
def test_bad_tokens__rejected(token: str) -> None:
    with pytest.raises(AppError) as e:
        _verifier().verify(token)
    assert e.value.code == "INVALID_CREDENTIALS"


def test_token_without_app_role__forbidden() -> None:
    with pytest.raises(AppError) as e:
        _verifier().verify(_token(roles=("offline_access",)))
    assert e.value.code == "FORBIDDEN"


def test_oidc_mode__password_sign_in_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    from planner.main import app

    monkeypatch.setattr(security.settings, "auth_mode", "oidc")
    c = TestClient(app)
    r = c.post("/api/v1/auth/login", json={"email": "a@b.co", "password": "x" * 12})
    assert (r.status_code, r.json()["code"]) == (403, "SSO_REQUIRED")
    r = c.post("/api/v1/auth/refresh", headers={"X-Requested-With": "XMLHttpRequest"})
    assert r.json()["code"] == "SSO_REQUIRED"
