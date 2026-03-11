from __future__ import annotations

from sql_migration_review_assistant.models import MigrationFile
from sql_migration_review_assistant.parser import parse_migration_file
from sql_migration_review_assistant.rules.safety import (
    DescriptionCommentMissingRule,
    ParseErrorRule,
    RollbackCommentMissingRule,
)


def test_rollback_comment_missing_rule(default_config) -> None:
    migration = MigrationFile(
        path="x.sql", relative_path="x.sql", content="CREATE TABLE x (id INT);"
    )
    parse_migration_file(migration, "postgres")

    issues = RollbackCommentMissingRule().check_file(migration, default_config)

    assert len(issues) == 1
    assert issues[0].rule_id == "safety.rollback_comment_missing"


def test_parse_error_rule(default_config) -> None:
    migration = MigrationFile(
        path="x.sql", relative_path="x.sql", content="CREAT TABLE broken(id INT);"
    )
    parse_migration_file(migration, "postgres")

    issues = ParseErrorRule().check_statement(migration, migration.statements[0], default_config)

    assert len(issues) == 1
    assert issues[0].severity.value == "error"
    assert "dialect='postgres'" in issues[0].message


def test_description_comment_rule_accepts_intro_comment_after_blank_lines(default_config) -> None:
    migration = MigrationFile(
        path="x.sql",
        relative_path="x.sql",
        content="\n\n-- Description: add users table\nCREATE TABLE users (id INT);",
    )
    parse_migration_file(migration, "postgres")

    issues = DescriptionCommentMissingRule().check_file(migration, default_config)

    assert issues == []
