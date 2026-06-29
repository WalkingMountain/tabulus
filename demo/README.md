# Tabulus redactor demo

Records the before/after that is the whole pitch: an agent sampling a real table,
with and without PII redaction.

## Run it

```bash
# 1. throwaway Postgres (any will do)
export DATABASE_URL=postgres://postgres:dev@localhost:5433/postgres

# 2. install + seed fake-PII table
pip install -e .
psql "$DATABASE_URL" -f demo/seed.sql

# 3a. just watch it
bash demo/record.sh

# 3b. or record the GIF the README embeds (output path must match)
asciinema rec -c "bash demo/record.sh" demo/tabulus-redactor.cast
agg demo/tabulus-redactor.cast demo/tabulus-redactor.gif
```

All seed values are fake. Point this at a scratch database only — never prod.
