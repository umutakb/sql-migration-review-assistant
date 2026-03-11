"""Terminal reporting with Rich."""

from __future__ import annotations

from collections import Counter

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..models import ReportBundle, ReviewIssue, ReviewStatus


def _status_style(status: ReviewStatus) -> str:
    if status == ReviewStatus.FAIL:
        return "bold red"
    if status == ReviewStatus.WARNING:
        return "bold yellow"
    return "bold green"


def _top_issues(issues: list[ReviewIssue], limit: int = 10) -> list[ReviewIssue]:
    return sorted(
        issues,
        key=lambda issue: (
            -issue.severity.rank,
            -issue.weight,
            issue.file_path,
            issue.statement_index or 0,
        ),
    )[:limit]


def _rule_breakdown(issues: list[ReviewIssue], limit: int = 8) -> list[tuple[str, int]]:
    counts = Counter(issue.rule_id for issue in issues)
    return counts.most_common(limit)


def render_terminal_report(
    bundle: ReportBundle,
    report_title: str,
    console: Console | None = None,
) -> None:
    """Render rich terminal summary report."""

    console = console or Console()

    summary = bundle.summary

    summary_table = Table.grid(padding=(0, 2))
    summary_table.add_column(style="bold cyan")
    summary_table.add_column()
    summary_table.add_row("Scanned Files", str(summary.scanned_files))
    summary_table.add_row("Total Statements", str(summary.total_statements))
    summary_table.add_row("Total Issues", str(summary.total_issues))
    summary_table.add_row("Errors", str(summary.errors))
    summary_table.add_row("Warnings", str(summary.warnings))
    summary_table.add_row("Info", str(summary.info))
    summary_table.add_row("Total Risk Score", f"{summary.total_risk_score:.2f}")
    summary_table.add_row(
        "Status", f"[{_status_style(bundle.status)}]{bundle.status.value.upper()}[/]"
    )
    console.print(Panel(summary_table, title=report_title, border_style="cyan"))

    meta_table = Table.grid(padding=(0, 2))
    meta_table.add_column(style="bold cyan")
    meta_table.add_column()
    meta_table.add_row("Input Path", bundle.input_path)
    meta_table.add_row("Generated At", bundle.generated_at.isoformat())
    meta_table.add_row("Tool Version", bundle.tool_version)
    console.print(Panel(meta_table, title="Metadata", border_style="blue"))

    file_table = Table(title="Top Risky Files", header_style="bold")
    file_table.add_column("File")
    file_table.add_column("Risk", justify="right")
    file_table.add_column("Errors", justify="right")
    file_table.add_column("Warnings", justify="right")
    file_table.add_column("Info", justify="right")

    top_files = sorted(bundle.file_summaries, key=lambda f: f.risk_score, reverse=True)[:10]
    if top_files:
        for item in top_files:
            file_table.add_row(
                item.file_path,
                f"{item.risk_score:.2f}",
                str(item.errors),
                str(item.warnings),
                str(item.info),
            )
    else:
        file_table.add_row("No files scanned", "-", "-", "-", "-")
    console.print(file_table)

    breakdown_table = Table(title="Rule Breakdown", header_style="bold")
    breakdown_table.add_column("Rule")
    breakdown_table.add_column("Count", justify="right")
    rule_rows = _rule_breakdown(bundle.issues)
    if rule_rows:
        for rule_id, count in rule_rows:
            breakdown_table.add_row(rule_id, str(count))
    else:
        breakdown_table.add_row("No issues detected", "0")
    console.print(breakdown_table)

    findings_table = Table(title="Top Findings", header_style="bold")
    findings_table.add_column("Severity")
    findings_table.add_column("Rule")
    findings_table.add_column("File")
    findings_table.add_column("Stmt", justify="right")
    findings_table.add_column("Message")

    top_findings = _top_issues(bundle.issues, limit=15)
    if top_findings:
        for issue in top_findings:
            findings_table.add_row(
                issue.severity.value,
                issue.rule_id,
                issue.file_path,
                str(issue.statement_index or "-"),
                issue.message,
            )
    else:
        findings_table.add_row("info", "-", "-", "-", "No findings detected.")

    console.print(findings_table)
