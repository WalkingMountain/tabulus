"""PII / secret redactor for tool output before LLM sees it.

Database tools (sample_rows, safe_select, describe_schema's sample_rows)
return rows from user tables. Those rows often contain customer emails,
API keys, JWTs, credit cards, SSNs, phone numbers, IPs. Without redaction
that data ships to Anthropic on every query — brand-killing leak.

Sentinel format: `[REDACTED:type]` — preserves enough structure for the
LLM to reason ("Stripe call failed with [REDACTED:api_key]") without
leaking the value.

Conservative philosophy: false positives are cheap, false negatives kill.

Off by default — set VIGIL_REDACT=on to enable.
"""

from __future__ import annotations

import os
import re
from typing import Any


_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # ── JWT (eyJ... three segments) ─────────────────────────────────────────
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")),
    # ── Vendor API keys with distinctive prefixes ───────────────────────────
    ("anthropic_key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}")),
    ("openai_key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9]{20,}")),
    ("stripe_key", re.compile(r"\b(?:sk|pk|rk)_(?:live|test)_[A-Za-z0-9]{20,}")),
    ("github_token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}")),
    ("slack_token", re.compile(r"\bxox[bpars]-[A-Za-z0-9-]{20,}")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    # ── Bearer / Authorization headers ──────────────────────────────────────
    ("bearer_token", re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/-]{20,}={0,2}")),
    # ── Credit card (13-19 digits, common groupings) ────────────────────────
    ("credit_card", re.compile(r"\b(?:\d[ -]*?){13,19}\b")),
    # ── SSN (US) ────────────────────────────────────────────────────────────
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    # ── Email ───────────────────────────────────────────────────────────────
    (
        "email",
        re.compile(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?"
            r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+\b"
        ),
    ),
    # ── Phone (international + US, conservative) ────────────────────────────
    (
        "phone",
        re.compile(
            r"(?<![A-Za-z0-9])\+?\d{1,3}[\s.-]?\(?\d{2,4}\)?"
            r"[\s.-]?\d{3,4}[\s.-]?\d{3,4}(?![A-Za-z0-9])"
        ),
    ),
    # ── IPv4 ────────────────────────────────────────────────────────────────
    ("ipv4", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    # ── IPv6 (handles :: compression, blocks Class::Path false matches) ─────
    (
        "ipv6",
        re.compile(r"(?<![A-Za-z0-9:])(?:[A-Fa-f0-9]{0,4}:){2,}[A-Fa-f0-9]{0,4}(?![A-Za-z0-9:])"),
    ),
]


def is_enabled() -> bool:
    return os.environ.get("VIGIL_REDACT", "off").lower() in ("on", "true", "1", "yes")


def redact_string(s: str) -> str:
    """Replace sensitive substrings with `[REDACTED:type]` sentinels. Idempotent."""
    if not isinstance(s, str) or not s:
        return s
    out = s
    for kind, pattern in _PATTERNS:
        out = pattern.sub(f"[REDACTED:{kind}]", out)
    return out


def redact_value(v: Any) -> Any:
    """Recursively redact str / list / dict / tuple. Dict KEYS NOT redacted."""
    if isinstance(v, str):
        return redact_string(v)
    if isinstance(v, dict):
        return {k: redact_value(val) for k, val in v.items()}
    if isinstance(v, list):
        return [redact_value(item) for item in v]
    if isinstance(v, tuple):
        return tuple(redact_value(item) for item in v)
    return v


def maybe_redact(v: Any) -> Any:
    """No-op when VIGIL_REDACT is off, redact otherwise."""
    return redact_value(v) if is_enabled() else v
