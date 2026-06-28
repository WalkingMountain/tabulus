"""Runtime config from environment variables."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    database_url: str
    max_rows: int            # cap on rows returned by any tool
    sample_size: int         # rows per describe_schema sample
    statement_timeout_ms: int
    allow_writes: bool       # default False — agent gets read-only


def load() -> Config:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is required. Set to a Postgres connection string "
            "(postgres://user:pass@host:5432/dbname)."
        )
    return Config(
        database_url=url,
        max_rows=int(os.environ.get("VIGIL_MAX_ROWS", "100")),
        sample_size=int(os.environ.get("VIGIL_SAMPLE_SIZE", "3")),
        statement_timeout_ms=int(os.environ.get("VIGIL_STATEMENT_TIMEOUT_MS", "5000")),
        allow_writes=os.environ.get("VIGIL_ALLOW_WRITES", "false").lower() == "true",
    )
