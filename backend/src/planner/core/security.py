"""JWT auth, password hashing, role guards (Backend.md)."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from pydantic import BaseModel, ConfigDict

from planner.core.config import settings
from planner.core.db import uuid7
from planner.core.errors import AppError

_ph = PasswordHash.recommended()
_bearer_security = HTTPBearer(auto_error=False)


def _to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])


def hash_password(plain: str) -> str:
    """Hash a password with Argon2id via pwdlib."""
    return _ph.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain password against its Argon2id hash."""
    return _ph.verify(plain, hashed)


def create_access_token(user_id: UUID, role: str) -> str:
    """Create a short-lived JWT access token with sub/role/jti claims."""
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "jti": uuid7().hex,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_access_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


class TokenVerifier:
    """Verifier hiding token verification behind an interface for future OIDC."""

    def __init__(self, secret: str, algorithm: str = "HS256") -> None:
        self.secret = secret
        self.algorithm = algorithm

    def verify(self, token: str) -> dict[str, Any]:
        """Verify and decode a JWT, raising AppError('INVALID_CREDENTIALS') on failure."""
        try:
            return jwt.decode(token, self.secret, algorithms=[self.algorithm])
        except Exception as exc:
            raise AppError("INVALID_CREDENTIALS") from exc


# Highest privilege first: a user holding several realm roles gets the strongest one
# (one role per user is the app's model, OQ-21).
APP_ROLES = ("administrator", "data_engineer", "auditor", "viewer")


class KeycloakTokenVerifier:
    """AUTH_MODE=oidc (Level 3 D-2): accept RS256 access tokens issued by the Keycloak
    realm, signed by a key from its JWKS (the realm's published public keys), and map
    the realm roles onto the app's four roles. MFA is enforced by Keycloak itself (the
    realm requires a TOTP authenticator), so every token it issues to a person has
    passed it."""

    def __init__(self, issuer: str, jwks_url: str = "") -> None:
        self.issuer = issuer.rstrip("/")
        self._jwks = jwt.PyJWKClient(
            jwks_url or f"{self.issuer}/protocol/openid-connect/certs", cache_keys=True
        )

    def verify(self, token: str) -> dict[str, Any]:
        try:
            key = self._jwks.get_signing_key_from_jwt(token).key
            payload: dict[str, Any] = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                issuer=self.issuer,
                # ponytail: every client of the realm is trusted; pin `azp` to the
                # app's client ids if the realm ever hosts other applications.
                options={"verify_aud": False, "require": ["exp", "iss", "sub"]},
            )
        except Exception as exc:
            raise AppError("INVALID_CREDENTIALS") from exc
        roles = set(payload.get("realm_access", {}).get("roles", []))
        role = next((r for r in APP_ROLES if r in roles), None)
        if role is None:
            raise AppError("FORBIDDEN")
        return {**payload, "role": role}


token_verifier: TokenVerifier | KeycloakTokenVerifier = (
    KeycloakTokenVerifier(settings.oidc_issuer, settings.oidc_jwks_url)
    if settings.auth_mode == "oidc"
    else TokenVerifier(settings.jwt_secret, settings.jwt_algorithm)
)


def decode_access_token(token: str) -> dict[str, Any]:
    """Helper to decode access token using the default verifier."""
    return token_verifier.verify(token)


class RequestPrincipal(BaseModel):
    """The authenticated caller extracted from the JWT."""

    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)

    user_id: UUID
    role: str
    email: str | None = None  # from the OIDC token; used to provision SSO users


async def get_current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_security),
) -> RequestPrincipal:
    """FastAPI dependency: extracts caller identity from Bearer token."""
    if credentials is None or not credentials.credentials:
        raise AppError("INVALID_CREDENTIALS")

    payload = token_verifier.verify(credentials.credentials)
    sub = payload.get("sub")
    role = payload.get("role")
    if not sub or not role:
        raise AppError("INVALID_CREDENTIALS")

    try:
        user_id = UUID(str(sub))
    except (ValueError, TypeError) as exc:
        raise AppError("INVALID_CREDENTIALS") from exc

    return RequestPrincipal(user_id=user_id, role=str(role), email=payload.get("email"))


# Alias for backwards compatibility
current_user = get_current_principal


def require_roles(*roles: str) -> Any:
    """FastAPI dependency: require principal to have one of the given roles."""

    async def _role_guard(
        principal: RequestPrincipal = Depends(get_current_principal),
    ) -> RequestPrincipal:
        if principal.role not in roles:
            raise AppError("FORBIDDEN")
        return principal

    return _role_guard


def hash_token(token: str) -> str:
    """Compute sha256 hex digest of a token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_refresh_token() -> tuple[str, str]:
    """Generate (opaque_token_hex, sha256_hex_of_token)."""
    opaque_token = secrets.token_hex(32)
    token_hash = hash_token(opaque_token)
    return opaque_token, token_hash


def require_local_auth() -> None:
    """Dependency for password sign-in routes: under AUTH_MODE=oidc every sign-in goes
    through Keycloak, so a password login here would bypass SSO and MFA."""
    if settings.auth_mode != "local":
        raise AppError("SSO_REQUIRED")
