"""Tests for the PII redactor."""

import os
from unittest.mock import patch

import pytest

from tabulus.redactor import (
    is_enabled,
    maybe_redact,
    redact_string,
    redact_value,
)


# ── Each pattern must redact ────────────────────────────────────────────────


@pytest.mark.parametrize(
    "payload,kind",
    [
        (
            "token eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
            "jwt",
        ),
        ("key sk-ant-api03-abcdefghijklmnopqrstuvwxyz", "anthropic_key"),
        ("sk-proj-aBcDeFgHiJkLmNoPqRsTuVwXyZ1234567890", "openai_key"),
        ("sk_live_4eC39HqLyjWDarjtT1zdp7dc", "stripe_key"),
        ("ghp_abcdefghijklmnopqrstuvwxyz0123456789", "github_token"),
        ("xoxb-1234567890-abcdefghijklmnopqrst", "slack_token"),
        ("AKIAIOSFODNN7EXAMPLE", "aws_access_key"),
        ("AIzaSyDdI0hCZtE6vySjMm-WEfRq3CPzqKqqsHI", "google_api_key"),
        ("Authorization: Bearer abcdef0123456789abcdef0123456789", "bearer_token"),
        ("Authorization: Token a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6", "bearer_token"),
        ("ssn 123-45-6789", "ssn"),
        ("Customer foo@example.com", "email"),
        ("call +1 415-555-1234", "phone"),
        ("at 192.168.1.42", "ipv4"),
        ("addr ::1 down", "ipv6"),
        ("card 4111 1111 1111 1111", "credit_card"),
        # ── regression: adversarial false-negatives found in audit ──────────
        (
            "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA\n-----END RSA PRIVATE KEY-----",
            "private_key",
        ),
        ("ya29.a0AfH6SMBx7kJq_longtokenvaluehere1234567890abcdef", "google_oauth"),
        ("aws_secret_access_key=wJalrXUtnFEMIK7MDENGbPxRfiCYEXAMPLEKEY", "secret"),
        ("api_key: 9f8e7d6c5b4a39281706f5e4d3c2b1a0", "secret"),
        ("client_secret='abcdef123456ghijkl'", "secret"),
        ("call +91 98765 43210", "phone"),  # international, 5-5 grouping
        ("ring (415) 555-0132 now", "phone"),  # US parens form
    ],
)
def test_pattern_redacted(payload, kind):
    out = redact_string(payload)
    assert f"[REDACTED:{kind}]" in out, f"{kind!r} not redacted in {payload!r} → {out!r}"


# ── Idempotency + structure preservation ───────────────────────────────────


def test_idempotent():
    s = "user cj@ex.com and key sk-ant-abc123def456ghi789jklmnopqrstuv"
    once = redact_string(s)
    twice = redact_string(once)
    assert once == twice


def test_hostnames_preserved():
    """`cache-prod-3.internal:6379` is diagnostic, not PII."""
    out = redact_string("cache-prod-3.internal:6379 refused")
    assert "cache-prod-3.internal" in out
    assert "6379" in out


def test_class_paths_preserved():
    """`Redis::ConnectionError` is structure, not PII."""
    out = redact_string("Redis::ConnectionError on OrderProcessor.perform")
    assert "Redis::ConnectionError" in out
    assert "OrderProcessor.perform" in out


# ── Nested structures ──────────────────────────────────────────────────────


def test_nested_dict():
    inp = {"user": "alice@example.com", "id": 42, "card": "4242 4242 4242 4242"}
    out = redact_value(inp)
    assert out["user"] == "[REDACTED:email]"
    assert out["id"] == 42
    assert "[REDACTED:credit_card]" in out["card"]
    # Keys not redacted (they're field names)
    assert "user" in out


def test_list_of_rows():
    rows = [
        {"email": "a@x.com", "amount": 100},
        {"email": "b@y.com", "amount": 200},
    ]
    out = redact_value(rows)
    assert out[0]["email"] == "[REDACTED:email]"
    assert out[1]["email"] == "[REDACTED:email]"
    assert out[0]["amount"] == 100


def test_secret_column_value_masked():
    """A value in a secret-named column is masked regardless of its content —
    a bare password has no in-text signal, so we key off the column name."""
    inp = {
        "id": 7,
        "name": "Jane",
        "db_password": "hunter2supersecret",
        "user_api_key": "plainlookingvalue123",
        "oauth_token": "nostructurehere",
        "city": "Berlin",
    }
    out = redact_value(inp)
    assert out["db_password"] == "[REDACTED:secret]"
    assert out["user_api_key"] == "[REDACTED:secret]"
    assert out["oauth_token"] == "[REDACTED:secret]"
    # Non-secret columns untouched
    assert out["name"] == "Jane"
    assert out["city"] == "Berlin"
    assert out["id"] == 7


def test_no_false_positive_number_runs():
    """Bare digit runs and UUIDs must NOT be mistaken for phone numbers."""
    assert redact_string("years 2020 2021 2022 were busy") == "years 2020 2021 2022 were busy"
    uuid = "550e8400-e29b-41d4-a716-446655440000"
    assert redact_string(uuid) == uuid


def test_benign_keyvalue_preserved():
    """key=value where the key isn't secret-y stays intact (no over-redaction)."""
    assert redact_string("monkey=banana12345") == "monkey=banana12345"
    assert redact_string("status=active") == "status=active"


def test_non_string_passthrough():
    assert redact_value(42) == 42
    assert redact_value(3.14) == 3.14
    assert redact_value(True) is True
    assert redact_value(None) is None


# ── Empty / edge cases ─────────────────────────────────────────────────────


def test_empty_string():
    assert redact_string("") == ""


def test_no_pii_unchanged():
    assert redact_string("plain text") == "plain text"


# ── maybe_redact respects env var ──────────────────────────────────────────


def test_disabled_by_default():
    with patch.dict(os.environ, {}, clear=True):
        assert is_enabled() is False
        # No redaction
        assert maybe_redact("foo@bar.com") == "foo@bar.com"


def test_enabled_via_env():
    with patch.dict(os.environ, {"TABULUS_REDACT": "on"}):
        assert is_enabled() is True
        assert maybe_redact("foo@bar.com") == "[REDACTED:email]"


def test_enabled_alt_values():
    for val in ("on", "ON", "true", "True", "1", "yes"):
        with patch.dict(os.environ, {"TABULUS_REDACT": val}):
            assert is_enabled() is True, f"TABULUS_REDACT={val!r} should enable"


def test_disabled_alt_values():
    for val in ("off", "false", "0", "no", "", "anything-else"):
        with patch.dict(os.environ, {"TABULUS_REDACT": val}):
            assert is_enabled() is False, f"TABULUS_REDACT={val!r} should NOT enable"
