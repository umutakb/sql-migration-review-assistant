"""Rules for locking and performance related risks."""

from __future__ import annotations

import re
from collections import defaultdict

from ..models import MigrationFile, ReviewIssue, Severity, StatementInfo, ToolConfig
from .base import Rule

_IDENTIFIER = r"[A-Za-z_\"\.][A-Za-z0-9_\"\.]*"


def _normalize(sql: str) -> str:
    return " ".join(sql.upper().split())


def _canonical_identifier(name: str) -> str:
    return name.strip().strip('"').lower()


def _parse_column_list(raw: str) -> list[str]:
    columns: list[str] = []
    for part in raw.split(","):
        token = part.strip().split()[0]
        if token:
            columns.append(_canonical_identifier(token))
    return columns


class MissingIndexForForeignKeyRule(Rule):
    rule_id = "performance.missing_index_for_foreign_key"
    title = "Foreign Key Without Supporting Index"
    description = "Warns when added foreign keys may miss supporting indexes."
    default_severity = Severity.WARNING
    default_weight = 4.0

    _fk_re = re.compile(
        rf"ALTER\s+TABLE\s+({_IDENTIFIER}).*?FOREIGN\s+KEY\s*\(([^)]+)\)",
        re.IGNORECASE | re.DOTALL,
    )
    _index_re = re.compile(
        rf"CREATE\s+(?:UNIQUE\s+)?INDEX(?:\s+CONCURRENTLY)?\s+{_IDENTIFIER}\s+ON\s+({_IDENTIFIER})\s*\(([^)]+)\)",
        re.IGNORECASE | re.DOTALL,
    )

    def check_file(self, file: MigrationFile, config: ToolConfig) -> list[ReviewIssue]:
        indexed_columns: dict[str, set[str]] = defaultdict(set)
        fk_columns: dict[str, set[str]] = defaultdict(set)

        for statement in file.statements:
            index_match = self._index_re.search(statement.raw_sql)
            if index_match:
                table = _canonical_identifier(index_match.group(1))
                for col in _parse_column_list(index_match.group(2)):
                    indexed_columns[table].add(col)

            fk_match = self._fk_re.search(statement.raw_sql)
            if fk_match:
                table = _canonical_identifier(fk_match.group(1))
                for col in _parse_column_list(fk_match.group(2)):
                    fk_columns[table].add(col)

        issues: list[ReviewIssue] = []
        for table, columns in fk_columns.items():
            missing = sorted(
                column for column in columns if column not in indexed_columns.get(table, set())
            )
            if missing:
                issues.append(
                    self.issue(
                        file=file,
                        config=config,
                        message=(
                            "Foreign key columns may be missing index on "
                            f"table '{table}': {', '.join(missing)}."
                        ),
                    )
                )

        return issues


class LargeTableMutationRule(Rule):
    rule_id = "performance.large_table_mutation"
    title = "Large Table Mutation Risk"
    description = "Highlights ALTER/UPDATE operations that may lock or scan many rows."
    default_severity = Severity.WARNING
    default_weight = 5.0

    def check_statement(
        self, file: MigrationFile, statement: StatementInfo, config: ToolConfig
    ) -> list[ReviewIssue]:
        sql = _normalize(statement.raw_sql)

        if re.match(r"^ALTER TABLE\b", sql):
            return [
                self.issue(
                    file=file,
                    statement=statement,
                    config=config,
                    message=(
                        "ALTER TABLE may acquire strong locks and impact " "high-traffic workloads."
                    ),
                )
            ]

        if re.match(r"^UPDATE\b", sql):
            if " WHERE " in f" {sql} ":
                message = (
                    "UPDATE can still impact many rows; validate execution "
                    "plan and batching strategy."
                )
            else:
                message = (
                    "UPDATE without WHERE can touch every row and generate "
                    "heavy write amplification."
                )

            return [self.issue(file=file, statement=statement, config=config, message=message)]

        return []


class CreateIndexWithoutConcurrentlyRule(Rule):
    rule_id = "performance.create_index_without_concurrently"
    title = "CREATE INDEX Without CONCURRENTLY"
    description = "Warns when PostgreSQL index creation may block writes."
    default_severity = Severity.WARNING
    default_weight = 6.0

    def check_statement(
        self, file: MigrationFile, statement: StatementInfo, config: ToolConfig
    ) -> list[ReviewIssue]:
        sql = _normalize(statement.raw_sql)
        if re.match(r"^CREATE\s+(?:UNIQUE\s+)?INDEX\b", sql) and " CONCURRENTLY " not in f" {sql} ":
            return [
                self.issue(
                    file=file,
                    statement=statement,
                    config=config,
                    message=(
                        "Consider CREATE INDEX CONCURRENTLY to reduce write "
                        "lock impact in PostgreSQL."
                    ),
                )
            ]
        return []


class TableRewriteRiskRule(Rule):
    rule_id = "performance.table_rewrite_risk"
    title = "Potential Table Rewrite Risk"
    description = "Marks ALTER patterns that can trigger expensive rewrites."
    default_severity = Severity.WARNING
    default_weight = 6.0

    def check_statement(
        self, file: MigrationFile, statement: StatementInfo, config: ToolConfig
    ) -> list[ReviewIssue]:
        sql = _normalize(statement.raw_sql)
        if not re.match(r"^ALTER TABLE\b", sql):
            return []

        risky_patterns = [
            r"\bALTER COLUMN\b.*\b(TYPE|SET DATA TYPE)\b",
            r"\bALTER COLUMN\b.*\bSET NOT NULL\b",
            r"\bADD COLUMN\b.*\bDEFAULT\b.*\bNOT NULL\b",
        ]

        if any(re.search(pattern, sql) for pattern in risky_patterns):
            return [
                self.issue(
                    file=file,
                    statement=statement,
                    config=config,
                    message=(
                        "This ALTER TABLE pattern may rewrite table data and "
                        "hold locks for extended periods."
                    ),
                )
            ]

        return []
