"""Rules for destructive SQL operations."""

from __future__ import annotations

import re

from ..models import MigrationFile, ReviewIssue, Severity, StatementInfo, ToolConfig
from .base import Rule


def _normalize(sql: str) -> str:
    return " ".join(sql.upper().split())


class DropTableRule(Rule):
    rule_id = "destructive.drop_table"
    title = "DROP TABLE Detected"
    description = "Detects table drops that are destructive."
    default_severity = Severity.ERROR
    default_weight = 12.0

    def check_statement(
        self, file: MigrationFile, statement: StatementInfo, config: ToolConfig
    ) -> list[ReviewIssue]:
        sql = _normalize(statement.raw_sql)
        if re.match(r"^DROP TABLE\b", sql):
            return [
                self.issue(
                    file=file,
                    statement=statement,
                    config=config,
                    message="DROP TABLE is destructive and typically irreversible in production.",
                )
            ]
        return []


class DropColumnRule(Rule):
    rule_id = "destructive.drop_column"
    title = "DROP COLUMN Detected"
    description = "Detects column drops that can break reads/writes."
    default_severity = Severity.ERROR
    default_weight = 10.0

    def check_statement(
        self, file: MigrationFile, statement: StatementInfo, config: ToolConfig
    ) -> list[ReviewIssue]:
        sql = _normalize(statement.raw_sql)
        if "DROP COLUMN" in sql:
            return [
                self.issue(
                    file=file,
                    statement=statement,
                    config=config,
                    message="DROP COLUMN may cause data loss and backward compatibility issues.",
                )
            ]
        return []


class TruncateRule(Rule):
    rule_id = "destructive.truncate"
    title = "TRUNCATE Detected"
    description = "Detects truncate operations that wipe entire tables."
    default_severity = Severity.ERROR
    default_weight = 10.0

    def check_statement(
        self, file: MigrationFile, statement: StatementInfo, config: ToolConfig
    ) -> list[ReviewIssue]:
        sql = _normalize(statement.raw_sql)
        if re.match(r"^TRUNCATE\b", sql):
            return [
                self.issue(
                    file=file,
                    statement=statement,
                    config=config,
                    message=(
                        "TRUNCATE removes all rows and is usually unsafe "
                        "without backup/restore plans."
                    ),
                )
            ]
        return []


class DeleteWithoutWhereRule(Rule):
    rule_id = "destructive.delete_without_where"
    title = "DELETE Without WHERE"
    description = "Detects DELETE statements missing WHERE clause."
    default_severity = Severity.ERROR
    default_weight = 9.0

    def check_statement(
        self, file: MigrationFile, statement: StatementInfo, config: ToolConfig
    ) -> list[ReviewIssue]:
        sql = _normalize(statement.raw_sql)
        if re.match(r"^DELETE FROM\b", sql) and " WHERE " not in f" {sql} ":
            return [
                self.issue(
                    file=file,
                    statement=statement,
                    config=config,
                    message="DELETE without WHERE may remove all rows in the target table.",
                )
            ]
        return []


class IrreversibleOperationRule(Rule):
    rule_id = "destructive.irreversible_operation"
    title = "Irreversible Operation Warning"
    description = "Highlights irreversible or hard-to-rollback operations."
    default_severity = Severity.WARNING
    default_weight = 5.0

    def check_statement(
        self, file: MigrationFile, statement: StatementInfo, config: ToolConfig
    ) -> list[ReviewIssue]:
        sql = _normalize(statement.raw_sql)
        irreversible_patterns = (
            r"^DROP TABLE\b",
            r"DROP COLUMN",
            r"^TRUNCATE\b",
            r"\bCASCADE\b",
        )
        if any(re.search(pattern, sql) for pattern in irreversible_patterns):
            return [
                self.issue(
                    file=file,
                    statement=statement,
                    config=config,
                    message=(
                        "This statement appears irreversible; ensure rollback "
                        "strategy and backups exist."
                    ),
                )
            ]
        return []
