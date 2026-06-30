# Security

Tabulus exists to put a safety boundary between an AI agent and your database.
This document states what it actually guarantees — and, just as importantly,
what it does not.

## Read-only enforcement

Read-only is enforced in **three independent layers**, so no single bug opens a
write path:

1. **Application keyword gate** (`safety.assert_read_only`) — strips comments,
   rejects multi-statement SQL, and requires a read-only lead keyword.
2. **Postgres transaction mode** — the connection pool sets
   `default_transaction_read_only=on` as a server setting. This is the real
   backstop: even if a query slips the gate, Postgres itself refuses the write.
3. **Row cap + statement timeout** — `safe_select` wraps user SQL so a
   user-supplied `LIMIT` can't bypass the cap, and a server-side
   `statement_timeout` bounds runtime.

Writes are only possible if you explicitly set `TABULUS_ALLOW_WRITES=true`,
which flips layers 1 and 2 off. Leave it unset in any environment you care about.

## The redactor — guarantees and limits

The PII/secret redactor (`TABULUS_REDACT=on`) is **best-effort defense in
depth, not a guarantee.** Its philosophy is deliberate: false positives are
cheap, false negatives are costly, so it errs toward over-redaction.

**It does redact:** emails, vendor API keys (Anthropic/OpenAI/Stripe/GitHub/
AWS/Slack/Google), OAuth and bearer tokens, JWTs, PEM private keys, credit
cards, US SSNs, international and US phone numbers, IPv4/IPv6, `key=value`
secrets, and any value sitting in a secret-named column.

**Known limits (it will NOT catch):**
- Bare high-entropy blobs with no prefix or signal (e.g. a raw base64 secret in
  an unnamed column) — too indistinguishable from legitimate data to redact
  without unacceptable false positives.
- Non-US national identifiers (NINO, Aadhaar, etc.).
- Domain-specific secrets with no recognizable shape.

Treat the redactor as a strong reduction in exposure, not a compliance
guarantee. If you handle regulated data, do not rely on it as your only control.

## Reporting a vulnerability

Please report security issues privately via GitHub's
[security advisory](https://github.com/WalkingMountain/tabulus/security/advisories/new)
flow rather than a public issue. We aim to acknowledge within a few days.

When reporting, include a reproduction and the impact (e.g. "value of type X
reaches tool output with `TABULUS_REDACT=on`"). Redactor false-negatives are
in scope and welcomed.
