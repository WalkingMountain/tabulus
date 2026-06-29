#!/usr/bin/env bash
# Scare-then-relieve demo. Records cleanly under asciinema:
#   asciinema rec -c "demo/record.sh" tabulus-redactor.cast
# Then: agg tabulus-redactor.cast tabulus-redactor.gif   (or upload the .cast)
#
# Requires: a throwaway Postgres + DATABASE_URL set, and `pip install -e .`
# Seed first:  psql "$DATABASE_URL" -f demo/seed.sql
set -euo pipefail

: "${DATABASE_URL:?set DATABASE_URL to a throwaway Postgres, e.g. postgres://postgres:dev@localhost:5433/postgres}"

pause() { sleep "${1:-1.4}"; }
say()   { printf '\n\033[1;36m# %s\033[0m\n' "$1"; pause 1.2; }

# Run sample_rows through Tabulus' own db layer, redactor toggled by env.
sample() {
  python - <<'PY'
import asyncio, json, os
from tabulus.config import load
from tabulus.db import get_pool, sample_rows, close_pool
async def main():
    pool = await get_pool(load())
    rows = await sample_rows(pool, "customers", 2)
    print(json.dumps(rows, indent=2, default=str))
    await close_pool()
asyncio.run(main())
PY
}

clear
say "Your AI agent samples a 'customers' table. Watch what reaches the model."
pause 1.6

say "WITHOUT Tabulus redaction (TABULUS_REDACT=off) — this is what most DB MCP servers send to the LLM:"
TABULUS_REDACT=off sample
pause 2.8

say "Emails. Stripe live keys. JWTs. Credit cards. SSNs. All shipped to Anthropic/OpenAI."
pause 2.4

say "WITH Tabulus (TABULUS_REDACT=on) — same query, scrubbed before the agent sees a thing:"
TABULUS_REDACT=on sample
pause 3.0

say "The agent still reasons over the shape. Your customers' data never left the building."
pause 2.0
printf '\n\033[1;32m  pip install tabulus  ·  TABULUS_REDACT=on\033[0m\n\n'
pause 2.0
