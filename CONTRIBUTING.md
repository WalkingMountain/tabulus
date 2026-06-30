# Contributing to Tabulus

Thanks for considering a contribution. Tabulus is a small, focused tool — a
read-only Postgres MCP server with a PII/secret redactor — so contributions
that sharpen that core are the most welcome.

## Development setup

```bash
git clone https://github.com/WalkingMountain/tabulus
cd tabulus
pip install -e ".[dev]"      # installs pytest, pytest-asyncio, ruff
```

## Before you open a PR

```bash
ruff format .                # apply formatting (CI enforces --check)
ruff check .                 # lint
pytest tests/ -v             # unit tests (pure logic, no DB needed)
```

CI runs on Python 3.11 and 3.12 and additionally exercises the DB layer against
a live Postgres service. The unit tests (`test_safety.py`, `test_redactor.py`)
need no database.

## Conventions

- Python ≥3.11, line length 100, double quotes (ruff defaults).
- Conventional Commits for messages (`feat:`, `fix:`, `docs:`, `chore:`).

## Especially welcome

- **Redactor coverage.** New secret/PII patterns with a test case, or a
  documented false-negative. The redactor's whole job is to never leak — see
  [SECURITY.md](./SECURITY.md). Pair every new pattern with a false-positive
  check so we don't over-redact benign data.
- **Connection-failure ergonomics.** Clearer error messages for common
  misconfigurations.

## Adding a tool

If you add an MCP tool that returns table data, route its output through
`redactor.maybe_redact`, and gate any raw user SQL through
`safety.assert_read_only`. Declare the tool in `server.list_tools`, dispatch it
in `call_tool`, and document any new env var in the README and `cli.py --help`.

## Scope

Tabulus is Postgres-only and read-only by design. Write support and other
databases are deliberate non-goals for the core; please open an issue to discuss
before building large features so we can align on direction.
