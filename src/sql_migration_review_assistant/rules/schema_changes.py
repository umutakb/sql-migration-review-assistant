"""Rules for schema evolution risks."""

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


class AlterColumnTypeRule(Rule):
    rule_id = "schema.alter_column_type"
    title = "ALTER COLUMN TYPE"
    description = "Detects column type changes that may lock or rewrite large tables."
    default_severity = Severity.WARNING
    default_weight = 6.0

    def check_statement(
        self, file: MigrationFile, statement: StatementInfo, config: ToolConfig
    ) -> list[ReviewIssue]:
        sql = _normalize(statement.raw_sql)
        if re.search(r"\bALTER TABLE\b", sql) and re.search(
            r"\bALTER COLUMN\b.*\b(TYPE|SET DATA TYPE)\b", sql
        ):
            return [
                self.issue(
                    file=file,
                    statement=statement,
                    config=config,
                    message="Column type modification can trigger table rewrite and long locks.",
                )
            ]
        return []


class NullableToNotNullRule(Rule):
    rule_id = "schema.nullable_to_not_null"
    title = "NULLABLE -> NOT NULL"
    description = "Detects NOT NULL enforcement changes."
    default_severity = Severity.WARNING
    default_weight = 6.0

    def check_statement(
        self, file: MigrationFile, statement: StatementInfo, config: ToolConfig
    ) -> list[ReviewIssue]:
        sql = _normalize(statement.raw_sql)
        if re.search(r"\bALTER TABLE\b", sql) and re.search(
            r"\bALTER COLUMN\b.*\bSET NOT NULL\b", sql
        ):
            return [
                self.issue(
                    file=file,
                    statement=statement,
                    config=config,
                    message="Setting NOT NULL may fail if existing rows contain NULL values.",
                )
            ]
        return []


class NotNullWithoutDefaultRule(Rule):
    rule_id = "schema.not_null_without_default"
    title = "NOT NULL Column Without DEFAULT"
    description = "Detects added NOT NULL columns lacking a default value."
    default_severity = Severity.ERROR
    default_weight = 9.0

    def check_statement(
        self, file: MigrationFile, statement: StatementInfo, config: ToolConfig
    ) -> list[ReviewIssue]:
        sql = _normalize(statement.raw_sql)
        if not re.search(r"\bALTER TABLE\b", sql):
            return []

        add_col_not_null = re.search(r"\bADD COLUMN\b.*\bNOT NULL\b", sql)
        if not add_col_not_null:
            return []

        has_default = re.search(r"\bDEFAULT\b", sql)
        default_is_null = re.search(r"\bDEFAULT\s+NULL\b", sql)
        has_identity_like_generation = re.search(r"\b(GENERATED|IDENTITY)\b", sql)
        has_serial_type = re.search(r"\b(SMALLSERIAL|SERIAL|BIGSERIAL)\b", sql)

        # Identity/serial columns are typically auto-populated and should not be
        # flagged by the "missing default" heuristic.
        if has_identity_like_generation or has_serial_type:
            return []

        if not has_default or default_is_null:
            reason = "DEFAULT is NULL" if default_is_null else "no DEFAULT is provided"
            return [
                self.issue(
                    file=file,
                    statement=statement,
                    config=config,
                    message=(
                        "Adding a NOT NULL column where "
                        f"{reason}. Existing rows may violate the constraint."
                    ),
                )
            ]

        return []


class EnumOrTypeNarrowingRule(Rule):
    rule_id = "schema.enum_or_type_narrowing"
    title = "Potential Enum/Type Narrowing"
    description = "Uses a basic heuristic for potentially narrowing column domain."
    default_severity = Severity.WARNING
    default_weight = 5.0

    def check_statement(
        self, file: MigrationFile, statement: StatementInfo, config: ToolConfig
    ) -> list[ReviewIssue]:
        sql = _normalize(statement.raw_sql)

        varchar_match = re.search(r"\bTYPE\s+VARCHAR\s*\((\d+)\)", sql)
        if varchar_match and int(varchar_match.group(1)) <= 64:
            return [
                self.issue(
                    file=file,
                    statement=statement,
                    config=config,
                    message=(
                        "Column type changed to a smaller VARCHAR length. "
                        "Validate existing data width "
                        "before deployment."
                    ),
                )
            ]

        if re.search(r"\bALTER TYPE\b", sql) and re.search(r"\bRENAME VALUE\b", sql):
            return [
                self.issue(
                    file=file,
                    statement=statement,
                    config=config,
                    message=(
                        "Enum value changes can break application assumptions; "
                        "verify compatibility."
                    ),
                )
            ]

        return []


class RenameDropAddHeuristicRule(Rule):
    rule_id = "schema.rename_drop_add_heuristic"
    title = "Potential Rename via DROP+ADD"
    description = "Warns when DROP COLUMN and ADD COLUMN happen together on a table."
    default_severity = Severity.INFO
    default_weight = 2.0

    _drop_re = re.compile(
        rf"ALTER\s+TABLE\s+({_IDENTIFIER}).*?DROP\s+COLUMN\s+({_IDENTIFIER})",
        re.IGNORECASE | re.DOTALL,
    )
    _add_re = re.compile(
        rf"ALTER\s+TABLE\s+({_IDENTIFIER}).*?ADD\s+COLUMN\s+({_IDENTIFIER})",
        re.IGNORECASE | re.DOTALL,
    )

    def check_file(self, file: MigrationFile, config: ToolConfig) -> list[ReviewIssue]:
        drops: dict[str, set[str]] = defaultdict(set)
        adds: dict[str, set[str]] = defaultdict(set)

        for statement in file.statements:
            drop_match = self._drop_re.search(statement.raw_sql)
            if drop_match:
                table = _canonical_identifier(drop_match.group(1))
                column = _canonical_identifier(drop_match.group(2))
                drops[table].add(column)

            add_match = self._add_re.search(statement.raw_sql)
            if add_match:
                table = _canonical_identifier(add_match.group(1))
                column = _canonical_identifier(add_match.group(2))
                adds[table].add(column)

        issues: list[ReviewIssue] = []
        for table in sorted(set(drops).intersection(adds)):
            if drops[table] and adds[table]:
                issues.append(
                    self.issue(
                        file=file,
                        config=config,
                        message=(
                            f"Table '{table}' contains both DROP COLUMN and ADD COLUMN operations; "
                            "consider using RENAME COLUMN if intent is rename."
                        ),
                    )
                )

        return issues
