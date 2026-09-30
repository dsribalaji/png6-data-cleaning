"""Redaction of secrets, PII, and injection attempts (Backend.md, NFR-01, FR-045)."""

from __future__ import annotations

import copy
import json
import re
from typing import Any

# PII matching patterns
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_RE = re.compile(
    r"(?:\+?\d{1,4}[-.\s]?)?(?:\(?\d{2,4}\)?[-.\s]?)?\d{2,5}[-.\s]?(\d{4})\b"
)
API_KEY_RE = re.compile(
    r"\b(?:sk-[A-Za-z0-9_-]{16,}|gsk_[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9_-]{16,}|"
    r"Bearer\s+[A-Za-z0-9._-]{16,}|ey[A-Za-z0-9_-]{20,}|[A-Za-z0-9_-]{32,})\b"
)

# Known prompt injection signatures in data cells
INJECTION_PATTERNS: tuple[str, ...] = (
    "ignore previous instructions",
    "ignore all instructions",
    "system:",
    "delete all",
    "drop table",
    "disregard",
    "jailbreak",
    "<|system|>",
    "<|user|>",
    "<|assistant|>",
    "do anything now",
    "override instructions",
    "forget all instructions",
    "new instructions:",
)

SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "api_key",
        "apikey",
        "authorization",
        "password",
        "credential",
        "credential_ciphertext",
        "token",
        "secret",
    }
)


def redact_pii(text: str) -> str:
    """Mask email addresses (***@***), phone numbers (***-***-####), and API tokens (***)."""
    if not isinstance(text, str):
        return text
    # 1. Redact long API keys/tokens first
    result = API_KEY_RE.sub("***", text)
    # 2. Redact email addresses
    result = EMAIL_RE.sub("***@***", result)
    # 3. Redact phone numbers, keeping last 4 digits
    result = PHONE_RE.sub(lambda m: f"***-***-{m.group(1)}", result)
    return result


def mask_value(v: str) -> str:
    """Mask a single string value for PII."""
    if not isinstance(v, str):
        return v
    return redact_pii(v)


def detect_injection(text: str) -> bool:
    """Detect prompt injection attempts via case-insensitive pattern matching."""
    if not isinstance(text, str):
        return False
    lowered = text.lower()
    return any(p.lower() in lowered for p in INJECTION_PATTERNS)


def minimise_payload(data: dict[str, Any], allow_data_sharing: bool) -> dict[str, Any]:
    """Deep-walk payload dictionary to minimize data exposed to LLMs.

    For any dict key "samples" holding a list:
    - If allow_data_sharing is True: keep samples as-is.
    - If allow_data_sharing is False: keep first 5 samples, mask PII, and drop samples
      containing prompt injection patterns.

    Returns a new dict without mutating the input.
    """
    if not isinstance(data, dict):
        return data

    result: dict[str, Any] = {}
    for k, v in data.items():
        if k == "samples" and isinstance(v, list):
            if allow_data_sharing:
                result[k] = [
                    minimise_payload(item, allow_data_sharing=True)
                    if isinstance(item, dict)
                    else (copy.deepcopy(item) if isinstance(item, list) else item)
                    for item in v
                ]
            else:
                filtered: list[Any] = []
                for item in v[:5]:
                    if isinstance(item, str):
                        if detect_injection(item):
                            continue
                        filtered.append(redact_pii(item))
                    elif isinstance(item, dict):
                        if detect_injection(json.dumps(item)):
                            continue
                        filtered.append(minimise_payload(item, allow_data_sharing=False))
                    else:
                        filtered.append(item)
                result[k] = filtered
        elif isinstance(v, dict):
            result[k] = minimise_payload(v, allow_data_sharing)
        elif isinstance(v, list):
            result[k] = [
                minimise_payload(item, allow_data_sharing)
                if isinstance(item, dict)
                else item
                for item in v
            ]
        else:
            result[k] = v
    return result


def _redact_dict(d: dict[str, Any]) -> dict[str, Any]:
    res: dict[str, Any] = {}
    for k, v in d.items():
        if isinstance(k, str) and k.lower() in SENSITIVE_KEYS:
            res[k] = "***REDACTED***"
        elif isinstance(v, dict):
            res[k] = _redact_dict(v)
        elif isinstance(v, list):
            res[k] = [_redact_dict(item) if isinstance(item, dict) else item for item in v]
        else:
            res[k] = v
    return res


def redact_sensitive(_, __, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Structlog processor that redacts sensitive keys from log events.

    Replaces values of keys {api_key, apikey, authorization, password, credential,
    credential_ciphertext, token, secret} with '***REDACTED***'.

    Wire into structlog.configure(processors=[...]).
    """
    return _redact_dict(event_dict)
