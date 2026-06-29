# Vigil

**A Postgres MCP server built for AI agents.**

Vigil is the database workbench for the AI-augmented developer. Connect Claude
Code, Cursor, or any MCP-compatible client to your Postgres database and let
the agent introspect the schema, sample data, and write safe queries — without
copy-pasting schemas into chat windows.

## Why

Every modern dev workflow now includes an AI agent. Every DB GUI was designed
before that was true. Vigil flips the model: **the agent is a first-class user,
not a sidebar feature.**

What that means in practice:

- Schema introspection optimized for LLM context windows (compact JSON, foreign
  keys flattened, sample rows inline).
- Read-only by default — `INSERT`/`UPDATE`/`DELETE`/`DDL` are rejected at the
  gateway. Agent can't drop your tables.
- `EXPLAIN` exposed as a tool so the agent can reason about query plans before
  proposing optimizations.
- Statement timeout + row cap enforced server-side. No agent can DOS your
  database by accident.

## Status

**v0.0.1 — alpha.** Postgres only. Stdio MCP transport only. No GUI yet.

## Install

```bash
pip install tabulus
```

## Run

```bash
export DATABASE_URL=postgres://user:pass@host:5432/dbname
vigil
```

Then point your MCP client at the `vigil` command.

### Claude Code (project-level)

Create `.mcp.json` in your project root:

```jsonc
{
  "mcpServers": {
    "vigil": {
      "command": "vigil",
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
claude mcp add vigil "$(which vigil)" --env DATABASE_URL=postgres://user:pass@host:5432/dbname
```

### Cursor

Add to `~/.cursor/mcp_servers.json`:

```jsonc
{
  "mcpServers": {
    "vigil": {
      "command": "vigil",
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
| `VIGIL_MAX_ROWS` | `100` | Hard cap on rows returned by any tool |
| `VIGIL_SAMPLE_SIZE` | `3` | Sample rows included in `describe_schema` |
| `VIGIL_STATEMENT_TIMEOUT_MS` | `5000` | Server-side query timeout |
| `VIGIL_REDACT` | `off` | Set `on` to scrub PII (emails, API keys, JWTs, credit cards, phones, IPs) from `sample_rows`, `safe_select`, and `describe_schema` output before the agent sees it. Recommended for production. |
| `VIGIL_ALLOW_WRITES` | `false` | Set `true` to disable the write block (NOT recommended) |

## Roadmap

- v0.1 — Postgres parity, polished install
- v0.2 — SQLite adapter
- v0.3 — MySQL / MariaDB adapter
- v0.x — Tauri desktop GUI shell on top of the same core
- v1.0 — Stable, cross-platform, multi-DB

## License

MIT. See [LICENSE](./LICENSE).
