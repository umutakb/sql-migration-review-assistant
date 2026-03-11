from __future__ import annotations

from sql_migration_review_assistant.models import MigrationFile
from sql_migration_review_assistant.parser import parse_migration_file
from sql_migration_review_assistant.rules.schema_changes import (
    AlterColumnTypeRule,
    NotNullWithoutDefaultRule,
)


def test_alter_column_type_rule(default_config) -> None:
    migration = MigrationFile(
        path="x.sql",
        relative_path="x.sql",
        content="ALTER TABLE users ALTER COLUMN age TYPE BIGINT;",
    )
    parse_migration_file(migration, "postgres")

    issues = AlterColumnTypeRule().check_statement(
        migration, migration.statements[0], default_config
    )

    assert len(issues) == 1
    assert issues[0].rule_id == "schema.alter_column_type"


def test_not_null_without_default_rule(default_config) -> None:
    migration = MigrationFile(
        path="x.sql",
        relative_path="x.sql",
        content="ALTER TABLE users ADD COLUMN created_by TEXT NOT NULL;",
    )
    parse_migration_file(migration, "postgres")

    issues = NotNullWithoutDefaultRule().check_statement(
        migration, migration.statements[0], default_config
    )

    assert len(issues) == 1
    assert issues[0].severity.value == "error"
