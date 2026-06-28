"""MCP server entry point.

Exposes 5 tools over stdio:
- list_tables
- describe_schema
- sample_rows
- safe_select
- explain

Used by Claude Code / Cursor / any MCP client.
"""

import asyncio
import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from vigil.config import load
from vigil.db import (
    close_pool,
    describe_table,
    explain,
    get_pool,
    list_tables,
    safe_select,
    sample_rows,
)
from vigil.safety import UnsafeSQLError, assert_read_only


server = Server("vigil")


@server.list_tools()
async def list_available_tools() -> list[Tool]:
    return [
        Tool(
            name="list_tables",
            description="List all tables in the database with row count estimates and sizes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "schema": {
                        "type": "string",
                        "description": "Optional schema name to filter (e.g., 'public').",
                    }
                },
            },
        ),
        Tool(
            name="describe_schema",
            description=(
                "Describe a table: columns, types, primary key, foreign keys, indexes, "
                "and a small sample of rows. The single most useful tool for an agent "
                "trying to understand the data model."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "table": {
                        "type": "string",
                        "description": "Table name, optionally schema-qualified (e.g., 'public.users').",
                    }
                },
                "required": ["table"],
            },
        ),
        Tool(
            name="sample_rows",
            description="Return a random sample of rows from a table.",
            inputSchema={
                "type": "object",
                "properties": {
                    "table": {"type": "string"},
                    "limit": {"type": "integer", "default": 10},
                },
                "required": ["table"],
            },
        ),
        Tool(
            name="safe_select",
            description=(
                "Run a read-only SELECT query. INSERT/UPDATE/DELETE/DDL are rejected. "
                "Results are capped at the server's max_rows setting (default 100)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "A SELECT/WITH/EXPLAIN/SHOW statement.",
                    }
                },
                "required": ["sql"],
            },
        ),
        Tool(
            name="explain",
            description="Return the query plan for a SELECT statement (EXPLAIN FORMAT JSON).",
            inputSchema={
                "type": "object",
                "properties": {"sql": {"type": "string"}},
                "required": ["sql"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    config = load()
    pool = await get_pool(config)

    try:
        if name == "list_tables":
            result = await list_tables(pool, arguments.get("schema"))
        elif name == "describe_schema":
            result = await describe_table(pool, arguments["table"], config.sample_size)
        elif name == "sample_rows":
            limit = min(int(arguments.get("limit", 10)), config.max_rows)
            result = await sample_rows(pool, arguments["table"], limit)
        elif name == "safe_select":
            sql = arguments["sql"]
            assert_read_only(sql)
            result = await safe_select(pool, sql, config.max_rows)
        elif name == "explain":
            sql = arguments["sql"]
            assert_read_only(sql)
            result = await explain(pool, sql)
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

        return [TextContent(type="text", text=json.dumps(result, default=str, indent=2))]

    except UnsafeSQLError as e:
        return [TextContent(type="text", text=f"Rejected by safety policy: {e}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {type(e).__name__}: {e}")]


async def run() -> None:
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())
    await close_pool()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
