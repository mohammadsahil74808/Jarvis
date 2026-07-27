# vision/privacy.py
"""Privacy and secret masking utilities for JARVIS vision context.

Filters and redacts sensitive information such as API keys, bearer tokens,
passwords, credit card numbers, and private credentials before text is stored
or transmitted to LLM prompts.
"""

from __future__ import annotations

import re

# RegEx patterns for common credentials and secrets
SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("GEMINI_KEY", re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b")),
    ("GROQ_KEY", re.compile(r"\bgsk_[a-zA-Z0-9_\-]{20,}\b")),
    ("NVIDIA_KEY", re.compile(r"\bnvapi-[a-zA-Z0-9_\-]{40,}\b")),
    ("HF_KEY", re.compile(r"\bhf_[a-zA-Z0-9]{30,}\b")),
    ("OPENROUTER_KEY", re.compile(r"\bsk-or-[a-zA-Z0-9_\-]{30,}\b")),
    ("GENERIC_SK_KEY", re.compile(r"\bsk-[a-zA-Z0-9]{32,}\b")),
    ("BEARER_TOKEN", re.compile(r"Bearer\s+[a-zA-Z0-9\._\-]{20,}", re.I)),
    ("PASSWORD_FIELD", re.compile(r"(?:password|passwd|pwd|secret)\s*[:=]\s*['\"]?\S+['\"]?", re.I)),
    ("CREDIT_CARD", re.compile(r"\b(?:\d[ -]*?){13,16}\b")),
    ("AWS_KEY", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
]


def mask_secrets(text: str) -> str:
    """Scans input text and replaces sensitive credentials with [REDACTED_SECRET]."""
    if not text:
        return ""

    masked = text
    for name, pattern in SECRET_PATTERNS:
        masked = pattern.sub(f"[REDACTED_{name}]", masked)

    return masked


def is_app_excluded(app_name: str | None, excluded_apps: set[str]) -> bool:
    """Checks if active application is in the privacy exclusion list."""
    if not app_name:
        return False
    app_lower = app_name.lower()
    return any(ex in app_lower for ex in excluded_apps)
