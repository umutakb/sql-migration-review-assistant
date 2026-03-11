from __future__ import annotations

from sql_migration_review_assistant.models import MigrationFile
from sql_migration_review_assistant.parser import parse_migration_file
from sql_migration_review_assistant.rules.performance import (
    CreateIndexWithoutConcurrentlyRule,
    MissingIndexForForeignKeyRule,
)


def test_create_index_without_concurrently_rule(default_config) -> None:
    migration = MigrationFile(
        path="x.sql",
        relative_path="x.sql",
        content="CREATE INDEX idx_orders_status ON orders(status);",
    )
    parse_migration_file(migration, "postgres")

    issues = CreateIndexWithoutConcurrentlyRule().check_statement(
        migration, migration.statements[0], default_config
    )

    assert len(issues) == 1
    assert issues[0].rule_id == "performance.create_index_without_concurrently"


def test_missing_index_for_foreign_key_rule(default_config) -> None:
    sql = """
    ALTER TABLE orders
      ADD CONSTRAINT fk_orders_customer
      FOREIGN KEY (customer_id) REFERENCES customers(id);
    """
    migration = MigrationFile(path="x.sql", relative_path="x.sql", content=sql)
    parse_migration_file(migration, "postgres")

    issues = MissingIndexForForeignKeyRule().check_file(migration, default_config)

    assert len(issues) == 1
    assert "customer_id" in issues[0].message
