"""Rule engine orchestration."""

from __future__ import annotations

from collections.abc import Iterable

from . import __version__
from .models import MigrationFile, ReportBundle, ReviewIssue, ToolConfig
from .rules import get_default_rules
from .rules.base import Rule
from .scoring import build_file_summary, build_review_summary, determine_status
from .sequence import analyze_sequence
from .utils import utc_now


def _issue_sort_key(issue: ReviewIssue) -> tuple[int, float, str, int]:
    return (
        -issue.severity.rank,
        -issue.weight,
        issue.file_path,
        issue.statement_index or 0,
    )


class ReviewEngine:
    """Executes configured rules over parsed migration files."""

    def __init__(self, rules: Iterable[Rule] | None = None) -> None:
        self.rules = list(rules) if rules is not None else get_default_rules()

    def review(
        self,
        files: list[MigrationFile],
        config: ToolConfig,
        input_path: str,
        ordering_strategy: str = "lexicographic",
    ) -> ReportBundle:
        issues: list[ReviewIssue] = []
        file_summaries = []
        total_statements = 0

        for file in files:
            file_issues: list[ReviewIssue] = []

            for rule in self.rules:
                if config.is_rule_enabled(rule.rule_id):
                    file_issues.extend(rule.check_file(file, config))

            for statement in file.statements:
                total_statements += 1
                for rule in self.rules:
                    if config.is_rule_enabled(rule.rule_id):
                        file_issues.extend(rule.check_statement(file, statement, config))

            file_issues.sort(key=_issue_sort_key)
            issues.extend(file_issues)
            file_summaries.append(build_file_summary(file, file_issues))

        issues.sort(key=_issue_sort_key)
        file_summaries.sort(key=lambda item: item.risk_score, reverse=True)

        summary = build_review_summary(files, issues, total_statements)
        status = determine_status(summary, config.fail_threshold)
        sequence_summary, sequence_insights = analyze_sequence(files, ordering_strategy)

        return ReportBundle(
            tool_version=__version__,
            generated_at=utc_now(),
            input_path=input_path,
            scanned_files=[file.relative_path for file in files],
            summary=summary,
            file_summaries=file_summaries,
            issues=issues,
            sequence_summary=sequence_summary,
            sequence_insights=sequence_insights,
            status=status,
        )
