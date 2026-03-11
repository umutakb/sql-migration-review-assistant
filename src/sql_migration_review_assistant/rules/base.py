"""Base abstractions for review rules."""

from __future__ import annotations

from ..models import MigrationFile, ReviewIssue, Severity, StatementInfo, ToolConfig
from ..utils import sql_excerpt


class Rule:
    """Base class for all review rules."""

    rule_id: str = "base.rule"
    title: str = "Base Rule"
    description: str = ""
    default_severity: Severity = Severity.WARNING
    default_weight: float = 1.0

    def check_file(self, file: MigrationFile, config: ToolConfig) -> list[ReviewIssue]:
        return []

    def check_statement(
        self,
        file: MigrationFile,
        statement: StatementInfo,
        config: ToolConfig,
    ) -> list[ReviewIssue]:
        return []

    def issue(
        self,
        *,
        file: MigrationFile,
        config: ToolConfig,
        message: str,
        statement: StatementInfo | None = None,
    ) -> ReviewIssue:
        """Create ReviewIssue while applying config overrides."""

        severity = config.resolve_severity(self.rule_id, self.default_severity)
        weight = config.resolve_weight(self.rule_id, severity, self.default_weight)

        return ReviewIssue(
            rule_id=self.rule_id,
            title=self.title,
            message=message,
            severity=severity,
            weight=weight,
            file_path=file.relative_path,
            statement_index=statement.index if statement else None,
            statement_excerpt=sql_excerpt(statement.raw_sql) if statement else None,
        )
