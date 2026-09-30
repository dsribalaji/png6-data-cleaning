"""JWT auth, password hashing, role guards (Backend.md)."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
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
    now = datetime.now(timezone.utc)
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


token_verifier = TokenVerifier(settings.jwt_secret, settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """Helper to decode access token using the default verifier."""
    return token_verifier.verify(token)


class RequestPrincipal(BaseModel):
    """The authenticated caller extracted from the JWT."""

    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)

    user_id: UUID
    role: str


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

    return RequestPrincipal(user_id=user_id, role=str(role))


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
