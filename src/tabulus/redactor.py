"""PII / secret redactor for tool output before LLM sees it.

Database tools (sample_rows, safe_select, describe_schema's sample_rows)
return rows from user tables. Those rows often contain customer emails,
API keys, JWTs, credit cards, SSNs, phone numbers, IPs. Without redaction
that data ships to Anthropic on every query — brand-killing leak.

Sentinel format: `[REDACTED:type]` — preserves enough structure for the
LLM to reason ("Stripe call failed with [REDACTED:api_key]") without
leaking the value.

Conservative philosophy: false positives are cheap, false negatives kill.

Off by default — set TABULUS_REDACT=on to enable.
"""

from __future__ import annotations

import os
import re
from typing import Any


# Each entry is (kind, pattern, replacement). `replacement` may contain `\1`
# backreferences to preserve a captured prefix (used by secret_kv to keep the
# key name and mask only the value). Default replacement is the sentinel.
def _sentinel(kind: str) -> str:
    return f"[REDACTED:{kind}]"


_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    # ── PEM private key blocks (highest value — never let one leak) ──────────
    (
        "private_key",
        re.compile(
            r"-----BEGIN[A-Z0-9 ]*PRIVATE KEY-----.*?-----END[A-Z0-9 ]*PRIVATE KEY-----", re.DOTALL
        ),
        _sentinel("private_key"),
    ),
    # ── JWT (eyJ... three segments) ─────────────────────────────────────────
    (
        "jwt",
        re.compile(r"\beyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"),
        _sentinel("jwt"),
    ),
    # ── Vendor API keys with distinctive prefixes ───────────────────────────
    ("anthropic_key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}"), _sentinel("anthropic_key")),
    ("openai_key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9]{20,}"), _sentinel("openai_key")),
    (
        "stripe_key",
        re.compile(r"\b(?:sk|pk|rk)_(?:live|test)_[A-Za-z0-9]{20,}"),
        _sentinel("stripe_key"),
    ),
    (
        "github_token",
        re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}"),
        _sentinel("github_token"),
    ),
    ("slack_token", re.compile(r"\bxox[bpars]-[A-Za-z0-9-]{20,}"), _sentinel("slack_token")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b"), _sentinel("aws_access_key")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"), _sentinel("google_api_key")),
    # ── Google OAuth access token ───────────────────────────────────────────
    ("google_oauth", re.compile(r"\bya29\.[A-Za-z0-9._-]{20,}"), _sentinel("google_oauth")),
    # ── Generic secret in key=value / key: value form (keep key, mask value) ─
    # Gated on a secret-y key name so false positives stay low. Per the module's
    # philosophy, masking a benign value here is cheaper than leaking a real one.
    (
        "secret",
        re.compile(
            r"(?i)(\b\w*(?:password|passwd|pwd|secret|api[_-]?key|apikey|access[_-]?key"
            r"|access[_-]?token|client[_-]?secret|private[_-]?key|auth[_-]?token"
            r"|credentials?|token)\w*\s*[:=]\s*[\"']?)([^\s\"',;]{6,})"
        ),
        r"\1[REDACTED:secret]",
    ),
    # ── Bearer / Token authorization schemes ────────────────────────────────
    (
        "bearer_token",
        re.compile(r"(?i)\b(?:bearer|token)\s+[A-Za-z0-9._~+/-]{20,}={0,2}"),
        _sentinel("bearer_token"),
    ),
    # ── Credit card (13-19 digits, common groupings) ────────────────────────
    ("credit_card", re.compile(r"\b(?:\d[ -]*?){13,19}\b"), _sentinel("credit_card")),
    # ── SSN (US) ────────────────────────────────────────────────────────────
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), _sentinel("ssn")),
    # ── Email ───────────────────────────────────────────────────────────────
    (
        "email",
        re.compile(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?"
            r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+\b"
        ),
        _sentinel("email"),
    ),
    # ── Phone, international: requires a leading + (avoids matching bare number
    #    runs like "2020 2021 2022"). Groups need no internal separators. ─────
    (
        "phone",
        re.compile(
            r"(?<![A-Za-z0-9])\+\d{1,3}[\s.-]?\(?\d{2,5}\)?(?:[\s.-]?\d{2,5}){1,3}(?![A-Za-z0-9])"
        ),
        _sentinel("phone"),
    ),
    # ── Phone, US/local: requires separators between 3-3-4 groups ────────────
    (
        "phone",
        re.compile(r"(?<![A-Za-z0-9])\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}(?![A-Za-z0-9])"),
        _sentinel("phone"),
    ),
    # ── IPv4 ────────────────────────────────────────────────────────────────
    ("ipv4", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), _sentinel("ipv4")),
    # ── IPv6 (handles :: compression, blocks Class::Path false matches) ─────
    (
        "ipv6",
        re.compile(r"(?<![A-Za-z0-9:])(?:[A-Fa-f0-9]{0,4}:){2,}[A-Fa-f0-9]{0,4}(?![A-Za-z0-9:])"),
        _sentinel("ipv6"),
    ),
]


# Column/field names whose VALUE is a secret regardless of its content. A bare
# password or token sitting in its own field has no in-text signal (no `key=`
# prefix), so we key off the column name instead. Matched as a substring, so
# `db_password`, `user_api_key`, `oauth_token` all trigger.
_SECRET_KEY_RE = re.compile(
    r"(?i)(?:password|passwd|pwd|secret|api[_-]?key|apikey|access[_-]?key"
    r"|access[_-]?token|client[_-]?secret|private[_-]?key|auth[_-]?token"
    r"|credentials?|token)"
)


def is_enabled() -> bool:
    return os.environ.get("TABULUS_REDACT", "off").lower() in ("on", "true", "1", "yes")


def redact_string(s: str) -> str:
    """Replace sensitive substrings with `[REDACTED:type]` sentinels. Idempotent."""
    if not isinstance(s, str) or not s:
        return s
    out = s
    for _kind, pattern, replacement in _PATTERNS:
        out = pattern.sub(replacement, out)
    return out


def redact_value(v: Any) -> Any:
    """Recursively redact str / list / dict / tuple. Dict KEYS NOT redacted."""
    if isinstance(v, str):
        return redact_string(v)
    if isinstance(v, dict):
        out = {}
        for k, val in v.items():
            if (
                isinstance(k, str)
                and _SECRET_KEY_RE.search(k)
                and isinstance(val, (str, int, float))
                and val != ""
            ):
                out[k] = "[REDACTED:secret]"
            else:
                out[k] = redact_value(val)
        return out
    if isinstance(v, list):
        return [redact_value(item) for item in v]
    if isinstance(v, tuple):
        return tuple(redact_value(item) for item in v)
    return v


def maybe_redact(v: Any) -> Any:
    """No-op when TABULUS_REDACT is off, redact otherwise."""
    return redact_value(v) if is_enabled() else v
