from __future__ import annotations

from sql_migration_review_assistant.models import (
    FailThreshold,
    MigrationFile,
    ReviewIssue,
    ReviewSummary,
    Severity,
)
from sql_migration_review_assistant.scoring import build_file_summary, determine_status


def test_build_file_summary_risk_aggregation() -> None:
    migration = MigrationFile(path="x.sql", relative_path="x.sql", content="", statements=[])
    issues = [
        ReviewIssue(
            rule_id="a",
            title="A",
            message="msg",
            severity=Severity.ERROR,
            weight=10,
            file_path="x.sql",
        ),
        ReviewIssue(
            rule_id="b",
            title="B",
            message="msg",
            severity=Severity.WARNING,
            weight=3,
            file_path="x.sql",
        ),
    ]

    summary = build_file_summary(migration, issues)

    assert summary.risk_score == 13
    assert summary.errors == 1
    assert summary.warnings == 1


def test_determine_status_with_thresholds() -> None:
    summary = ReviewSummary(
        scanned_files=1,
        total_statements=2,
        total_issues=1,
        errors=1,
        warnings=0,
        info=0,
        total_risk_score=10,
    )

    status = determine_status(summary, FailThreshold(severity=Severity.ERROR, risk_score=20))
    assert status.value == "fail"
