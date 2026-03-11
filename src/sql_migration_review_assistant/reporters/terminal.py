"""Terminal reporting with Rich."""

from __future__ import annotations

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

    file_table = Table(title="Top Risky Files", header_style="bold")
    file_table.add_column("File")
    file_table.add_column("Risk", justify="right")
    file_table.add_column("Errors", justify="right")
    file_table.add_column("Warnings", justify="right")
    file_table.add_column("Info", justify="right")

    for item in sorted(bundle.file_summaries, key=lambda f: f.risk_score, reverse=True)[:10]:
        file_table.add_row(
            item.file_path,
            f"{item.risk_score:.2f}",
            str(item.errors),
            str(item.warnings),
            str(item.info),
        )

    console.print(file_table)

    findings_table = Table(title="Top Findings", header_style="bold")
    findings_table.add_column("Severity")
    findings_table.add_column("Rule")
    findings_table.add_column("File")
    findings_table.add_column("Stmt", justify="right")
    findings_table.add_column("Message")

    for issue in _top_issues(bundle.issues, limit=15):
        findings_table.add_row(
            issue.severity.value,
            issue.rule_id,
            issue.file_path,
            str(issue.statement_index or "-"),
            issue.message,
        )

    console.print(findings_table)
