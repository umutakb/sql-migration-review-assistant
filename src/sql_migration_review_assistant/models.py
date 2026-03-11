"""Domain models for SQL migration review workflow."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Severity(StrEnum):
    """Severity levels used by review issues."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

    @property
    def rank(self) -> int:
        return {Severity.ERROR: 3, Severity.WARNING: 2, Severity.INFO: 1}[self]


class ReviewStatus(StrEnum):
    """Overall status for a migration review."""

    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"


class FailThreshold(BaseModel):
    """Threshold controls used when deriving review status."""

    severity: Severity = Severity.ERROR
    risk_score: float = 25.0


class StatementInfo(BaseModel):
    """Parsed metadata for one SQL statement."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    index: int
    raw_sql: str
    statement_type: str
    table_names: list[str] = Field(default_factory=list)
    parsed: bool = True
    parse_error: str | None = None
    ast: Any | None = Field(default=None, repr=False, exclude=True)


class MigrationFile(BaseModel):
    """In-memory representation of a migration file."""

    path: str
    relative_path: str
    content: str
    statements: list[StatementInfo] = Field(default_factory=list)


class ReviewIssue(BaseModel):
    """One finding emitted by a rule."""

    rule_id: str
    title: str
    message: str
    severity: Severity
    weight: float
    file_path: str
    statement_index: int | None = None
    statement_excerpt: str | None = None


class ReviewSummary(BaseModel):
    """Aggregated summary over all scanned files."""

    scanned_files: int
    total_statements: int
    total_issues: int
    errors: int
    warnings: int
    info: int
    total_risk_score: float


class FileRiskSummary(BaseModel):
    """Per-file aggregation used in reports."""

    file_path: str
    statements: int
    issues: int
    errors: int
    warnings: int
    info: int
    risk_score: float


class ReportBundle(BaseModel):
    """All structured data for report generation."""

    tool_version: str
    generated_at: datetime
    input_path: str
    scanned_files: list[str]
    summary: ReviewSummary
    file_summaries: list[FileRiskSummary]
    issues: list[ReviewIssue]
    status: ReviewStatus


class ToolConfig(BaseModel):
    """Configuration model for rule and reporting behavior."""

    report_title: str = "SQL Migration Review Report"
    dialect: str = "postgres"
    enabled_rules: dict[str, bool] = Field(default_factory=dict)
    severity_overrides: dict[str, Severity] = Field(default_factory=dict)
    fail_threshold: FailThreshold = Field(default_factory=FailThreshold)
    risk_weights: dict[str, float] = Field(default_factory=dict)
    ignored_paths: list[str] = Field(default_factory=list)

    def is_rule_enabled(self, rule_id: str) -> bool:
        return self.enabled_rules.get(rule_id, True)

    def resolve_severity(self, rule_id: str, default: Severity) -> Severity:
        return self.severity_overrides.get(rule_id, default)

    def resolve_weight(self, rule_id: str, severity: Severity, default: float) -> float:
        if rule_id in self.risk_weights:
            return float(self.risk_weights[rule_id])

        severity_key = f"severity.{severity.value}"
        if severity_key in self.risk_weights:
            return float(self.risk_weights[severity_key])

        return default
