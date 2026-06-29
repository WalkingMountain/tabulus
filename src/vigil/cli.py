"""CLI entry point — `vigil` command.

Wraps startup errors in friendly messages so the agent / user sees actionable
hints instead of stack traces.
"""

import sys

from vigil import __version__


def main() -> None:
    if "--version" in sys.argv or "-V" in sys.argv:
        print(f"vigil {__version__}")
        return

    if "--help" in sys.argv or "-h" in sys.argv:
        print(
            "vigil — Postgres MCP server for AI agents\n"
            "\n"
            "Usage:\n"
            "  DATABASE_URL=postgres://user:pass@host:5432/dbname vigil\n"
            "\n"
            "Environment variables:\n"
            "  DATABASE_URL              required — Postgres connection string\n"
            "  VIGIL_MAX_ROWS            default 100 — cap on rows returned\n"
            "  VIGIL_SAMPLE_SIZE         default 3 — rows in describe_schema sample\n"
            "  VIGIL_STATEMENT_TIMEOUT_MS  default 5000 — server-side query timeout\n"
            "  VIGIL_REDACT              default off — set 'on' to scrub PII from output\n"
            "  VIGIL_ALLOW_WRITES        default false — keep false (read-only)\n"
            "\n"
            "Repo: https://github.com/WalkingMountain/vigil"
        )
        return

    try:
        # Defer import so --version/--help don't pay the asyncio + mcp cost
        from vigil.config import load
        from vigil.server import main as run_server

        # Fast-fail config validation BEFORE we open the stdio MCP loop —
        # otherwise the agent waits until first tool call to learn DATABASE_URL
        # is missing, which makes the failure mode confusing.
        load()
        run_server()
    except RuntimeError as e:
        # Config errors (missing DATABASE_URL, etc.) — already friendly
        print(f"vigil: {e}", file=sys.stderr)
        sys.exit(2)
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        # Last resort — show error class + message, hint at common causes
        print(
            f"vigil: unexpected error: {type(e).__name__}: {e}\n"
            f"\n"
            f"Common causes:\n"
            f"  - DATABASE_URL points at an unreachable host\n"
            f"  - Postgres requires SSL but the URL lacks ?sslmode=require\n"
            f"  - User in DATABASE_URL lacks CONNECT or USAGE privileges\n"
            f"\n"
            f"File an issue: https://github.com/WalkingMountain/vigil/issues",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
