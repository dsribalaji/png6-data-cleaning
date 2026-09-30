"""Fernet symmetric encryption for model credentials at rest (Backend.md, FR-048)."""

from __future__ import annotations

from cryptography.fernet import Fernet

from planner.core.config import settings
from planner.modules.model_config.errors import CONFIGURATION_ERROR


def _get_fernet() -> Fernet:
    """Retrieve configured Fernet cipher or raise CONFIGURATION_ERROR."""
    key = settings.fernet_key
    if not key or "change-me" in key.lower():
        raise CONFIGURATION_ERROR
    try:
        return Fernet(key.encode("utf-8"))
    except Exception as exc:
        raise CONFIGURATION_ERROR from exc


def encrypt_credential(plaintext: str) -> str:
    """Encrypt a plaintext API credential using Fernet."""
    fernet = _get_fernet()
    try:
        return fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")
    except Exception as exc:
        raise CONFIGURATION_ERROR from exc


def decrypt_credential(ciphertext: str) -> str:
    """Decrypt a Fernet-encrypted ciphertext API credential."""
    fernet = _get_fernet()
    try:
        return fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except Exception as exc:
        raise CONFIGURATION_ERROR from exc


def credential_last4(plaintext: str) -> str:
    """Extract the last 4 characters of a credential string ("" if empty)."""
    if not plaintext:
        return ""
    return plaintext[-4:]
