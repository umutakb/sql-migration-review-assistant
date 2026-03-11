from __future__ import annotations

from pathlib import Path

from sql_migration_review_assistant.loader import load_migration_files
from sql_migration_review_assistant.parser import parse_migration_file, split_sql_statements


def test_split_sql_statements_respects_comments_and_quotes() -> None:
    sql = """
    -- comment with ;
    INSERT INTO test (name) VALUES ('semi;colon');
    CREATE TABLE x (id INT);
    """
    chunks = split_sql_statements(sql)

    assert len(chunks) == 2
    assert chunks[0].startswith("-- comment")
    assert "CREATE TABLE" in chunks[1]


def test_parse_migration_file_reports_parse_error(fixture_dir: Path) -> None:
    paths = [fixture_dir / "invalid.sql"]
    migration = load_migration_files(paths, root=fixture_dir)[0]

    parsed = parse_migration_file(migration, dialect="postgres")

    assert len(parsed.statements) == 1
    assert parsed.statements[0].parsed is False
    assert parsed.statements[0].parse_error
