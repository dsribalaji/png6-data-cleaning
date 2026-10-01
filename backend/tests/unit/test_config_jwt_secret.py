"""NFR-01: the JWT signing key must be at least 32 bytes and not the .env.example placeholder."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from planner.core.config import Settings


@pytest.mark.parametrize("secret", ["short", "replace-with-a-random-secret-of-at-least-32-bytes"])
def test_settings__weak_jwt_secret__rejected(secret: str) -> None:
    with pytest.raises(ValidationError):
        Settings(jwt_secret=secret)


def test_settings__32_byte_jwt_secret__accepted() -> None:
    assert Settings(jwt_secret="k" * 32).jwt_secret == "k" * 32
