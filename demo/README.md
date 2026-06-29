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

# 3b. or record a GIF
asciinema rec -c "bash demo/record.sh" tabulus-redactor.cast
agg tabulus-redactor.cast tabulus-redactor.gif
```

All seed values are fake. Point this at a scratch database only — never prod.
