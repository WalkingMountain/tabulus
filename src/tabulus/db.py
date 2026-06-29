"""Postgres connection pool + schema introspection.

LLM-friendly schema output: compact JSON, sample rows inline, foreign keys
flattened. Goal is to fit a 50-table schema into one prompt without truncation.
"""

import asyncpg
from typing import Any

from tabulus.config import Config
from tabulus.redactor import maybe_redact


_pool: asyncpg.Pool | None = None


async def get_pool(config: Config) -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            config.database_url,
            min_size=1,
            max_size=4,
            command_timeout=config.statement_timeout_ms / 1000.0,
            server_settings={
                "default_transaction_read_only": "off" if config.allow_writes else "on",
                "statement_timeout": str(config.statement_timeout_ms),
            },
        )
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def list_tables(pool: asyncpg.Pool, schema: str | None = None) -> list[dict[str, Any]]:
    """List tables. For tables Postgres hasn't ANALYZEd yet (reltuples < 0),
    fall back to a live COUNT(*) so the agent never sees `-1` row counts."""
    sql = """
        SELECT
            n.nspname     AS schema,
            c.relname     AS name,
            c.reltuples::bigint AS row_estimate,
            pg_size_pretty(pg_total_relation_size(c.oid)) AS size,
            obj_description(c.oid, 'pg_class') AS comment
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relkind IN ('r', 'p', 'v', 'm')
          AND n.nspname NOT IN ('pg_catalog', 'information_schema')
          AND ($1::text IS NULL OR n.nspname = $1)
        ORDER BY n.nspname, c.relname
    """
    rows = await pool.fetch(sql, schema)
    result = [dict(r) for r in rows]
    for row in result:
        if row["row_estimate"] is None or row["row_estimate"] < 0:
            try:
                count = await pool.fetchval(
                    f'SELECT COUNT(*) FROM "{row["schema"]}"."{row["name"]}"'
                )
                row["row_estimate"] = int(count)
                row["row_estimate_exact"] = True
            except Exception:
                row["row_estimate"] = None
    return result


async def describe_table(
    pool: asyncpg.Pool,
    qualified: str,
    sample_size: int,
) -> dict[str, Any]:
    """Return columns, indexes, foreign keys, and a small sample."""
    schema, table = _split_qualified(qualified)

    columns = await pool.fetch(
        """
        SELECT
            column_name AS name,
            data_type AS type,
            is_nullable = 'YES' AS nullable,
            column_default AS default,
            character_maximum_length AS max_length
        FROM information_schema.columns
        WHERE table_schema = $1 AND table_name = $2
        ORDER BY ordinal_position
        """,
        schema,
        table,
    )

    primary_key = await pool.fetch(
        """
        SELECT a.attname AS column
        FROM pg_index i
        JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
        WHERE i.indrelid = ($1 || '.' || $2)::regclass AND i.indisprimary
        """,
        schema,
        table,
    )

    foreign_keys = await pool.fetch(
        """
        SELECT
            kcu.column_name AS from_column,
            ccu.table_schema || '.' || ccu.table_name AS to_table,
            ccu.column_name AS to_column
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage ccu
          ON ccu.constraint_name = tc.constraint_name
         AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_schema = $1
          AND tc.table_name = $2
        """,
        schema,
        table,
    )

    indexes = await pool.fetch(
        """
        SELECT indexname AS name, indexdef AS definition
        FROM pg_indexes
        WHERE schemaname = $1 AND tablename = $2
        """,
        schema,
        table,
    )

    sample = await pool.fetch(
        f'SELECT * FROM "{schema}"."{table}" LIMIT $1',
        sample_size,
    )

    return {
        "table": f"{schema}.{table}",
        "columns": [dict(c) for c in columns],
        "primary_key": [r["column"] for r in primary_key],
        "foreign_keys": [dict(f) for f in foreign_keys],
        "indexes": [dict(i) for i in indexes],
        "sample_rows": maybe_redact([dict(s) for s in sample]),
    }


async def sample_rows(
    pool: asyncpg.Pool,
    qualified: str,
    limit: int,
) -> list[dict[str, Any]]:
    schema, table = _split_qualified(qualified)
    rows = await pool.fetch(
        f'SELECT * FROM "{schema}"."{table}" ORDER BY random() LIMIT $1',
        limit,
    )
    return maybe_redact([dict(r) for r in rows])


async def safe_select(
    pool: asyncpg.Pool,
    sql: str,
    max_rows: int,
) -> dict[str, Any]:
    # Wrap with LIMIT enforcement (subquery prevents user-supplied LIMIT bypass)
    wrapped = f"SELECT * FROM ({sql}) _tabulus_q LIMIT {int(max_rows)}"
    rows = await pool.fetch(wrapped)
    return {
        "row_count": len(rows),
        "rows": maybe_redact([dict(r) for r in rows]),
        "truncated": len(rows) == max_rows,
    }


async def explain(pool: asyncpg.Pool, sql: str) -> dict[str, Any]:
    plan = await pool.fetchval(f"EXPLAIN (FORMAT JSON, ANALYZE FALSE) {sql}")
    return {"plan": plan}


def _split_qualified(qualified: str) -> tuple[str, str]:
    """Parse `schema.table` or bare `table` (assumes public)."""
    if "." in qualified:
        schema, table = qualified.split(".", 1)
    else:
        schema, table = "public", qualified
    # Reject injection vectors
    for part in (schema, table):
        if not all(c.isalnum() or c == "_" for c in part):
            raise ValueError(f"Invalid identifier: {part!r}")
    return schema, table
