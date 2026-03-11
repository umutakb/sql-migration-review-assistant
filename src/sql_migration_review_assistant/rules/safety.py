"""Rules for operational safety and review hygiene."""

from __future__ import annotations

import re

from ..models import MigrationFile, ReviewIssue, Severity, StatementInfo, ToolConfig
from .base import Rule


def _normalize(sql: str) -> str:
    return " ".join(sql.upper().split())


class RollbackCommentMissingRule(Rule):
    rule_id = "safety.rollback_comment_missing"
    title = "Rollback Note Missing"
    description = "Checks whether migration contains rollback guidance comment."
    default_severity = Severity.WARNING
    default_weight = 2.0

    def check_file(self, file: MigrationFile, config: ToolConfig) -> list[ReviewIssue]:
        lowered = file.content.lower()
        if any(token in lowered for token in ("rollback", "down migration", "revert")):
            return []

        return [
            self.issue(
                file=file,
                config=config,
                message="Migration comment does not include rollback/down guidance.",
            )
        ]


class DescriptionCommentMissingRule(Rule):
    rule_id = "safety.description_comment_missing"
    title = "Migration Description Missing"
    description = "Checks if migration starts with a descriptive comment."
    default_severity = Severity.INFO
    default_weight = 1.0

    def check_file(self, file: MigrationFile, config: ToolConfig) -> list[ReviewIssue]:
        first_non_empty: str | None = None
        for line in file.content.splitlines():
            stripped = line.strip()
            if stripped:
                first_non_empty = stripped
                break

        if first_non_empty and (
            first_non_empty.startswith("--") or first_non_empty.startswith("/*")
        ):
            return []

        return [
            self.issue(
                file=file,
                config=config,
                message="Start migration with a comment describing intent and expected impact.",
            )
        ]


class TransactionSafetyRule(Rule):
    rule_id = "safety.transaction_safety"
    title = "Transaction Safety Warning"
    description = "Flags risky transaction usage patterns in migration scripts."
    default_severity = Severity.WARNING
    default_weight = 3.0

    def check_file(self, file: MigrationFile, config: ToolConfig) -> list[ReviewIssue]:
        statements = file.statements
        if not statements:
            return []

        normalized_statements = [_normalize(statement.raw_sql) for statement in statements]
        has_begin = any(re.match(r"^BEGIN\b", sql) for sql in normalized_statements)
        has_commit = any(re.match(r"^COMMIT\b", sql) for sql in normalized_statements)
        has_concurrently = any("CREATE INDEX CONCURRENTLY" in sql for sql in normalized_statements)

        issues: list[ReviewIssue] = []

        if has_begin != has_commit:
            issues.append(
                self.issue(
                    file=file,
                    config=config,
                    message="Transaction block appears incomplete (BEGIN/COMMIT mismatch).",
                )
            )

        if has_concurrently and (has_begin or has_commit):
            issues.append(
                self.issue(
                    file=file,
                    config=config,
                    message=(
                        "CREATE INDEX CONCURRENTLY cannot run inside a "
                        "transaction block in PostgreSQL."
                    ),
                )
            )

        if len(statements) > 1 and not has_begin and not has_concurrently:
            issues.append(
                self.issue(
                    file=file,
                    config=config,
                    message="Multi-statement migration has no explicit transaction boundary.",
                )
            )

        return issues


class RawUpdateDeleteRule(Rule):
    rule_id = "safety.raw_update_delete"
    title = "Raw UPDATE/DELETE Caution"
    description = "Reminds reviewers to verify data mutations carefully."
    default_severity = Severity.INFO
    default_weight = 1.0

    def check_statement(
        self, file: MigrationFile, statement: StatementInfo, config: ToolConfig
    ) -> list[ReviewIssue]:
        sql = _normalize(statement.raw_sql)
        if re.match(r"^(UPDATE|DELETE)\b", sql):
            return [
                self.issue(
                    file=file,
                    statement=statement,
                    config=config,
                    message="Review data mutation for row scope, batching, and rollback strategy.",
                )
            ]
        return []


class ParseErrorRule(Rule):
    rule_id = "safety.parse_error"
    title = "Unparseable SQL Statement"
    description = "Emits a finding for SQL statements that fail parsing."
    default_severity = Severity.ERROR
    default_weight = 8.0

    def check_statement(
        self, file: MigrationFile, statement: StatementInfo, config: ToolConfig
    ) -> list[ReviewIssue]:
        if statement.parsed:
            return []

        detail = statement.parse_error or "Unknown parser error"
        return [
            self.issue(
                file=file,
                statement=statement,
                config=config,
                message=f"Statement could not be parsed by sqlglot: {detail}",
            )
        ]
