from __future__ import annotations

from sql_migration_review_assistant.models import MigrationFile
from sql_migration_review_assistant.parser import parse_migration_file
from sql_migration_review_assistant.rules.destructive import DeleteWithoutWhereRule, DropTableRule


def test_drop_table_rule_detects_drop(default_config) -> None:
    migration = MigrationFile(path="x.sql", relative_path="x.sql", content="DROP TABLE users;")
    parse_migration_file(migration, "postgres")
    rule = DropTableRule()

    issues = rule.check_statement(migration, migration.statements[0], default_config)

    assert len(issues) == 1
    assert issues[0].rule_id == "destructive.drop_table"


def test_delete_without_where_rule_detects_full_delete(default_config) -> None:
    migration = MigrationFile(path="x.sql", relative_path="x.sql", content="DELETE FROM users;")
    parse_migration_file(migration, "postgres")
    rule = DeleteWithoutWhereRule()

    issues = rule.check_statement(migration, migration.statements[0], default_config)

    assert len(issues) == 1
    assert issues[0].severity.value == "error"


def test_delete_without_where_rule_ignores_delete_with_where(default_config) -> None:
    migration = MigrationFile(
        path="x.sql", relative_path="x.sql", content="DELETE FROM users WHERE id = 1;"
    )
    parse_migration_file(migration, "postgres")
    rule = DeleteWithoutWhereRule()

    issues = rule.check_statement(migration, migration.statements[0], default_config)

    assert issues == []


def test_delete_without_where_rule_ignores_where_in_comment(default_config) -> None:
    migration = MigrationFile(
        path="x.sql",
        relative_path="x.sql",
        content="DELETE FROM users -- WHERE id = 1\n;",
    )
    parse_migration_file(migration, "postgres")
    rule = DeleteWithoutWhereRule()

    issues = rule.check_statement(migration, migration.statements[0], default_config)

    assert len(issues) == 1
