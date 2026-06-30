# Tabulus

**Let your AI agent query your real Postgres — without leaking customer data to the LLM.**

Tabulus is a Postgres MCP server that sits between your AI agent (Claude Code,
Cursor, any MCP client) and your database. It scrubs emails, API keys, JWTs,
credit cards, SSNs, phones, and IPs **out of every result before the agent ever
sees them** — so you can point Claude at a production-shaped database without
piping your customers' PII into someone else's model.

![Tabulus redactor: customer PII and secrets scrubbed before they reach the LLM](demo/tabulus-redactor.svg)

<sub>Same query, redactor off vs on — real output. Record the animated version yourself: [`demo/`](demo/).</sub>

## The problem

Connecting an AI agent to your database means every row it samples — every
customer email, every Stripe key sitting in a config table, every JWT in a
sessions row — gets shipped into the LLM's context window. To Anthropic. To
OpenAI. To wherever the model runs. Most DB MCP servers solve "can the agent
drop my tables." **Tabulus solves what leaves the building.**

```
Without redaction:   {"email": "jane@acme.com",  "api_key": "sk_live_4eC39Hq..."}
With Tabulus:        {"email": "[REDACTED:email]", "api_key": "[REDACTED:stripe_key]"}
```

Turn it on with `TABULUS_REDACT=on`. The sentinel keeps enough structure for the
agent to reason (`"Stripe call failed with [REDACTED:stripe_key]"`) without ever
seeing the secret.

## Also in the box

- **PII/secret redactor** — emails, API keys (Anthropic/OpenAI/Stripe/GitHub/AWS/
  Slack/Google), OAuth + bearer tokens, JWTs, PEM private keys, credit cards, SSNs,
  international + US phones, IPv4/IPv6 — plus `key=value` secrets and any value in a
  secret-named column (`password`, `api_key`, …). Conservative by design: false
  positives are cheap, false negatives leak.
- **Read-only, enforced three ways** — keyword gate + Postgres read-only
  transaction + row cap. The agent can't drop your tables.
- **Schema introspection tuned for context windows** — compact JSON, foreign keys
  flattened, sample rows inline. Fits a 50-table schema in one prompt.
- **`EXPLAIN` as a tool** — the agent reasons about query plans before proposing
  optimizations.
- **Statement timeout + row cap** server-side. No accidental DOS.

## Status

**v0.0.4 — alpha.** Postgres only. Stdio MCP transport only. No GUI yet.

## Install

```bash
pip install tabulus
```

## Run

```bash
export DATABASE_URL=postgres://user:pass@host:5432/dbname
tabulus
```

Then point your MCP client at the `tabulus` command.

### Claude Code (project-level)

Create `.mcp.json` in your project root:

```jsonc
{
  "mcpServers": {
    "tabulus": {
      "command": "tabulus",
      "args": [],
      "env": {
        "DATABASE_URL": "postgres://user:pass@host:5432/dbname"
      }
    }
  }
}
```

Restart Claude Code in that directory and approve the trust prompt.

### Claude Code (user-level via CLI)

```bash
claude mcp add tabulus "$(which tabulus)" --env DATABASE_URL=postgres://user:pass@host:5432/dbname
```

### Cursor

Add to `~/.cursor/mcp_servers.json`:

```jsonc
{
  "mcpServers": {
    "tabulus": {
      "command": "tabulus",
      "env": { "DATABASE_URL": "postgres://user:pass@host:5432/dbname" }
    }
  }
}
```

## Tools

| Tool | Description |
|---|---|
| `list_tables` | All tables with row count estimates + sizes |
| `describe_schema` | Columns, PK, FKs, indexes, sample rows for a table |
| `sample_rows` | Random sample from a table |
| `safe_select` | Run a read-only SELECT (write keywords rejected) |
| `explain` | Get query plan (EXPLAIN FORMAT JSON) |

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | — (required) | Postgres connection URL |
| `TABULUS_MAX_ROWS` | `100` | Hard cap on rows returned by any tool |
| `TABULUS_SAMPLE_SIZE` | `3` | Sample rows included in `describe_schema` |
| `TABULUS_STATEMENT_TIMEOUT_MS` | `5000` | Server-side query timeout |
| `TABULUS_REDACT` | `off` | Set `on` to scrub PII (emails, API keys, JWTs, credit cards, phones, IPs) from `sample_rows`, `safe_select`, and `describe_schema` output before the agent sees it. Recommended for production. |
| `TABULUS_ALLOW_WRITES` | `false` | Set `true` to disable the write block (NOT recommended) |

## For teams

Tabulus core is free and MIT — and stays that way. If your organization is letting
AI agents touch real, sensitive databases and you need **audit logs, centrally
enforced redaction policy, column-level masking, or SSO**, we're exploring a
self-hosted Team tier (your data never routes through us).

👉 **[Tell us what you'd need →](https://github.com/WalkingMountain/tabulus/issues/1)**

## Roadmap

- v0.1 — Postgres parity, polished install
- v0.2 — SQLite adapter
- v0.3 — MySQL / MariaDB adapter
- v0.x — Tauri desktop GUI shell on top of the same core
- v1.0 — Stable, cross-platform, multi-DB

## License

MIT. See [LICENSE](./LICENSE).
