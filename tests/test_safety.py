"""Tests for read-only SQL gating. False negatives here = data loss in user DBs."""

import pytest

from vigil.safety import UnsafeSQLError, assert_read_only, normalize


# ── Allowed: every safe lead keyword ────────────────────────────────────────

@pytest.mark.parametrize("sql", [
    "SELECT 1",
    "SELECT * FROM users",
    "WITH t AS (SELECT 1) SELECT * FROM t",
    "EXPLAIN SELECT 1",
    "SHOW search_path",
    "VALUES (1), (2), (3)",
    "TABLE users",
    "  select * from users  ",  # whitespace tolerated
    "SELECT * FROM users -- inline comment",
    "/* block */ SELECT 1",
])
def test_allows_read_only(sql):
    assert_read_only(sql)  # raises on failure


# ── Forbidden: every mutating keyword ───────────────────────────────────────

@pytest.mark.parametrize("sql", [
    "INSERT INTO users VALUES (1)",
    "UPDATE users SET name = 'x'",
    "DELETE FROM users",
    "DROP TABLE users",
    "TRUNCATE users",
    "ALTER TABLE users ADD COLUMN x int",
    "CREATE TABLE x (id int)",
    "GRANT ALL ON users TO public",
    "REVOKE SELECT ON users FROM public",
    "VACUUM users",
    "REINDEX TABLE users",
    "EXPLAIN ANALYZE SELECT 1",   # ANALYZE runs the query — unsafe by default
    "EXPLAIN ANALYZE DELETE FROM users",
    "COPY users FROM '/tmp/x.csv'",
    "DO $$ BEGIN INSERT INTO x VALUES (1); END $$",
    "CALL my_procedure()",
    "MERGE INTO users USING source ON id = id WHEN MATCHED THEN UPDATE SET x = 1",
    "REPLACE INTO users VALUES (1)",
])
def test_rejects_mutations(sql):
    with pytest.raises(UnsafeSQLError):
        assert_read_only(sql)


# ── Multi-statement attack ──────────────────────────────────────────────────

def test_rejects_multi_statement_smuggled_delete():
    with pytest.raises(UnsafeSQLError):
        assert_read_only("SELECT 1; DELETE FROM users")


def test_rejects_multi_statement_with_trailing_semicolon():
    # Trailing ; on single SELECT is OK
    assert_read_only("SELECT 1;")


# ── Comment-hidden attack ───────────────────────────────────────────────────

def test_rejects_keyword_hidden_in_comment_strip():
    """A DELETE hidden after a block comment must still be caught."""
    with pytest.raises(UnsafeSQLError):
        assert_read_only("SELECT 1 /* x */ ; DELETE FROM users")


def test_keyword_in_string_literal_still_rejected_conservatively():
    """SELECT * FROM users WHERE name = 'DELETE' contains the word DELETE.
    Conservative scanner errs on safety side. Acceptable false positive."""
    with pytest.raises(UnsafeSQLError):
        assert_read_only("SELECT * FROM users WHERE name = 'DELETE'")


# ── Empty / malformed ───────────────────────────────────────────────────────

def test_rejects_empty():
    with pytest.raises(UnsafeSQLError):
        assert_read_only("")


def test_rejects_whitespace_only():
    with pytest.raises(UnsafeSQLError):
        assert_read_only("   \n\t  ")


# ── normalize utility ───────────────────────────────────────────────────────

def test_normalize_strips_comments():
    assert "SELECT 1" in normalize("SELECT 1 -- comment\n")
    assert "comment" not in normalize("SELECT 1 -- comment\n")
    assert "SELECT 1" in normalize("/* hi */ SELECT 1")


def test_normalize_collapses_whitespace():
    assert normalize("SELECT\n\t1") == "SELECT 1"
