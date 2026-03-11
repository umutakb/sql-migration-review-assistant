"""Rules for operational safety and review hygiene."""

from __future__ import annotations

import re

from ..models import MigrationFile, ReviewIssue, Severity, StatementInfo, ToolConfig
from .base import Rule

_LINE_COMMENT_RE = re.compile(r"^\s*--\s?(.*)$")
_BLOCK_COMMENT_RE = re.compile(r"/\*(.*?)\*/", re.DOTALL)
_ROLLBACK_HINT_RE = re.compile(r"\b(roll\s?back|rollback|down migration|revert|undo)\b")


def _normalize(sql: str) -> str:
    return " ".join(sql.upper().split())


def _extract_comments(content: str) -> list[str]:
    comments: list[str] = []

    for line in content.splitlines():
        match = _LINE_COMMENT_RE.match(line)
        if match:
            comments.append(match.group(1).strip())

    for match in _BLOCK_COMMENT_RE.finditer(content):
        comments.append(match.group(1).strip())

    return comments


def _has_intro_comment(content: str, lookahead_non_empty_lines: int = 5) -> bool:
    non_empty_seen = 0
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        non_empty_seen += 1
        if stripped.startswith("--") or stripped.startswith("/*"):
            return True

        if non_empty_seen >= lookahead_non_empty_lines:
            return False

    return False


class RollbackCommentMissingRule(Rule):
    rule_id = "safety.rollback_comment_missing"
    title = "Rollback Note Missing"
    description = "Checks whether migration contains rollback guidance comment."
    default_severity = Severity.WARNING
    default_weight = 2.0

    def check_file(self, file: MigrationFile, config: ToolConfig) -> list[ReviewIssue]:
        comments = _extract_comments(file.content)
        if any(_ROLLBACK_HINT_RE.search(comment.lower()) for comment in comments):
            return []

        return [
            self.issue(
                file=file,
                config=config,
                message=(
                    "No rollback note found in migration comments. "
                    "Add a short down/rollback strategy for safer reviews."
                ),
            )
        ]


class DescriptionCommentMissingRule(Rule):
    rule_id = "safety.description_comment_missing"
    title = "Migration Description Missing"
    description = "Checks if migration starts with a descriptive comment."
    default_severity = Severity.INFO
    default_weight = 1.0

    def check_file(self, file: MigrationFile, config: ToolConfig) -> list[ReviewIssue]:
        if _has_intro_comment(file.content):
            return []

        return [
            self.issue(
                file=file,
                config=config,
                message=(
                    "Add an introductory comment near the top describing "
                    "migration intent and expected impact."
                ),
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

        detail = (statement.parse_error or "Unknown parser error").splitlines()[0]
        return [
            self.issue(
                file=file,
                statement=statement,
                config=config,
                message=(
                    "Failed to parse statement with sqlglot "
                    f"(dialect='{config.dialect}'). Error: {detail}. "
                    "Verify SQL syntax or adjust dialect in config."
                ),
            )
        ]
