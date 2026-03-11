"""Risk scoring and status evaluation utilities."""

from __future__ import annotations

from .models import (
    FailThreshold,
    FileRiskSummary,
    MigrationFile,
    ReviewIssue,
    ReviewStatus,
    ReviewSummary,
    Severity,
)


def _count_severity(issues: list[ReviewIssue], severity: Severity) -> int:
    return sum(1 for issue in issues if issue.severity == severity)


def build_file_summary(file: MigrationFile, file_issues: list[ReviewIssue]) -> FileRiskSummary:
    """Build per-file risk summary."""

    risk_score = sum(issue.weight for issue in file_issues)
    return FileRiskSummary(
        file_path=file.relative_path,
        statements=len(file.statements),
        issues=len(file_issues),
        errors=_count_severity(file_issues, Severity.ERROR),
        warnings=_count_severity(file_issues, Severity.WARNING),
        info=_count_severity(file_issues, Severity.INFO),
        risk_score=round(risk_score, 2),
    )


def build_review_summary(
    files: list[MigrationFile], issues: list[ReviewIssue], total_statements: int
) -> ReviewSummary:
    """Build final summary over all files and issues."""

    risk_score = sum(issue.weight for issue in issues)
    return ReviewSummary(
        scanned_files=len(files),
        total_statements=total_statements,
        total_issues=len(issues),
        errors=_count_severity(issues, Severity.ERROR),
        warnings=_count_severity(issues, Severity.WARNING),
        info=_count_severity(issues, Severity.INFO),
        total_risk_score=round(risk_score, 2),
    )


def determine_status(summary: ReviewSummary, threshold: FailThreshold) -> ReviewStatus:
    """Derive final status using severity and risk thresholds."""

    if threshold.severity == Severity.ERROR and summary.errors > 0:
        return ReviewStatus.FAIL
    if threshold.severity == Severity.WARNING and (summary.errors + summary.warnings) > 0:
        return ReviewStatus.FAIL
    if threshold.severity == Severity.INFO and summary.total_issues > 0:
        return ReviewStatus.FAIL

    if summary.total_risk_score >= threshold.risk_score:
        return ReviewStatus.FAIL

    if summary.total_issues > 0:
        return ReviewStatus.WARNING

    return ReviewStatus.PASS
