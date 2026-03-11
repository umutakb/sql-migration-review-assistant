from __future__ import annotations

from sql_migration_review_assistant.models import MigrationFile
from sql_migration_review_assistant.parser import parse_migration_file
from sql_migration_review_assistant.sequence import analyze_sequence


def _parsed(path: str, sql: str) -> MigrationFile:
    migration = MigrationFile(path=path, relative_path=path, content=sql)
    return parse_migration_file(migration, "postgres")


def test_sequence_summary_generation() -> None:
    files = [
        _parsed("001_create_users.sql", "CREATE TABLE users (id INT PRIMARY KEY);"),
        _parsed("002_update_users.sql", "UPDATE users SET id = id WHERE id > 0;"),
    ]

    summary, insights = analyze_sequence(files, ordering_strategy="numeric-prefix")

    assert summary.enabled is True
    assert summary.total_files == 2
    assert summary.ordering_strategy == "numeric-prefix"
    assert summary.insight_count == len(insights)


def test_rename_suspicion_heuristic() -> None:
    files = [
        _parsed("001_drop.sql", "ALTER TABLE orders DROP COLUMN status;"),
        _parsed("002_add.sql", "ALTER TABLE orders ADD COLUMN state TEXT;"),
    ]

    _, insights = analyze_sequence(files, ordering_strategy="numeric-prefix")

    assert any(item.kind == "rename_suspicion" for item in insights)


def test_repeated_table_touch_heuristic() -> None:
    files = [
        _parsed("001.sql", "ALTER TABLE accounts ADD COLUMN region TEXT;"),
        _parsed("002.sql", "UPDATE accounts SET region = 'eu' WHERE region IS NULL;"),
        _parsed("003.sql", "ALTER TABLE accounts ALTER COLUMN region SET NOT NULL;"),
    ]

    _, insights = analyze_sequence(files, ordering_strategy="numeric-prefix")

    assert any(item.kind == "repeated_table_touch" for item in insights)


def test_single_file_sequence_disabled() -> None:
    files = [_parsed("single.sql", "CREATE TABLE x (id INT);")]

    summary, insights = analyze_sequence(files, ordering_strategy="single-file")

    assert summary.enabled is False
    assert summary.insight_count == 0
    assert insights == []
