"""SQL safety — read-only enforcement.

Rejects any statement that could mutate data or schema. Default mode for the
agent: SELECT + EXPLAIN only. Writes only enabled when TABULUS_ALLOW_WRITES=true
AND the human operator opts in per-statement (future approval flow).
"""

import re

_FORBIDDEN_KEYWORDS = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "TRUNCATE",
    "ALTER",
    "CREATE",
    "GRANT",
    "REVOKE",
    "COMMENT",
    "REINDEX",
    "VACUUM",
    "ANALYZE",
    "CLUSTER",
    "COPY",
    "DO",
    "CALL",
    "MERGE",
    "REPLACE",
    "RENAME",
    "REFRESH",
    "LOCK",
    "NOTIFY",
    "LISTEN",
    "UNLISTEN",
    "SET",
    "RESET",
    "DISCARD",
    "PREPARE",
    "EXECUTE",
    "DEALLOCATE",
    "BEGIN",
    "COMMIT",
    "ROLLBACK",
    "SAVEPOINT",
    "RELEASE",
    "START",
}

# Statements that are always allowed in read-only mode
_ALLOWED_LEADS = {"SELECT", "WITH", "EXPLAIN", "SHOW", "TABLE", "VALUES"}


class UnsafeSQLError(ValueError):
    """Raised when a query would mutate state in read-only mode."""


def normalize(sql: str) -> str:
    """Strip comments and collapse whitespace for keyword inspection."""
    # Strip /* ... */ block comments
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    # Strip -- line comments
    sql = re.sub(r"--[^\n]*", " ", sql)
    return " ".join(sql.split())


def assert_read_only(sql: str) -> None:
    """Raise UnsafeSQLError if sql contains any mutating keyword.

    Approach: tokenize on word boundaries, reject if any forbidden keyword
    appears at statement-leading position OR after a semicolon.
    """
    cleaned = normalize(sql)
    if not cleaned:
        raise UnsafeSQLError("Empty statement")

    # Split on semicolons (multi-statement). Reject anything that isn't a
    # single read-only statement.
    statements = [s.strip() for s in cleaned.split(";") if s.strip()]
    if len(statements) > 1:
        raise UnsafeSQLError("Multiple statements not allowed in read-only mode")

    stmt = statements[0]
    first_word = stmt.split(None, 1)[0].upper()
    if first_word not in _ALLOWED_LEADS:
        raise UnsafeSQLError(
            f"Statement must start with one of {sorted(_ALLOWED_LEADS)} "
            f"in read-only mode (got {first_word!r})"
        )

    # Defense-in-depth: scan for any forbidden keyword anywhere
    upper_tokens = set(re.findall(r"\b[A-Z]+\b", stmt.upper()))
    forbidden_hits = upper_tokens & _FORBIDDEN_KEYWORDS
    if forbidden_hits:
        raise UnsafeSQLError(f"Forbidden keyword(s) in read-only mode: {sorted(forbidden_hits)}")
