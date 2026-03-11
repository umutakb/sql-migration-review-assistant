"""Typer CLI entrypoint for SQL Migration Review Assistant."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

import typer
from rich.console import Console

from . import __version__
from .config import load_config
from .engine import ReviewEngine
from .loader import collect_sql_paths, load_migration_files
from .models import ReviewStatus, Severity
from .parser import parse_migrations
from .reporters import render_terminal_report, write_html_report, write_json_report
from .utils import write_example_files

app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help=(
        "Review SQL migration files, detect risky changes, and produce "
        "terminal/JSON/HTML reports."
    ),
)
console = Console()


class OutputFormat(StrEnum):
    TERMINAL = "terminal"
    JSON = "json"
    HTML = "html"
    ALL = "all"


def _exit_with_error(message: str, hint: str | None = None, code: int = 2) -> None:
    typer.secho(f"Error: {message}", fg=typer.colors.RED, err=True)
    if hint:
        typer.secho(f"Hint: {hint}", fg=typer.colors.YELLOW, err=True)
    raise typer.Exit(code=code)


@app.command("review")
def review(
    migrations_path: Path = typer.Argument(
        ...,
        help="Path to a .sql file or directory containing .sql migration files.",
    ),
    format: OutputFormat = typer.Option(
        OutputFormat.TERMINAL,
        "--format",
        "-f",
        help="Report output: terminal, json, html, or all.",
        case_sensitive=False,
    ),
    output_dir: Path = typer.Option(
        Path("artifacts"),
        "--output-dir",
        "-o",
        help="Directory where JSON/HTML reports will be written.",
    ),
    config_path: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to config YAML. Defaults to ./config.yaml when present.",
    ),
    fail_on: Severity | None = typer.Option(
        None,
        "--fail-on",
        help="Override fail threshold severity: error | warning | info.",
        case_sensitive=False,
    ),
) -> None:
    """Analyze SQL migrations and generate risk findings."""

    try:
        config = load_config(config_path)
    except FileNotFoundError as exc:
        _exit_with_error(
            str(exc),
            "Provide a valid --config path or remove --config to use defaults.",
        )
    except ValueError as exc:
        _exit_with_error(
            str(exc),
            "Fix config schema/types and retry. See README config example.",
        )

    if fail_on is not None:
        config.fail_threshold.severity = fail_on

    try:
        sql_paths = collect_sql_paths(migrations_path, config.ignored_paths)
    except FileNotFoundError as exc:
        _exit_with_error(str(exc), "Provide an existing .sql file or directory path.")
    except ValueError as exc:
        _exit_with_error(
            str(exc),
            "Input must be a .sql file or a directory containing .sql files.",
        )

    if not sql_paths:
        typer.secho(
            "No SQL files found for analysis after applying ignore/exclude patterns.",
            fg=typer.colors.YELLOW,
            err=True,
        )
        raise typer.Exit(code=1)

    root = migrations_path if migrations_path.is_dir() else migrations_path.parent
    migrations = load_migration_files(sql_paths, root=root)
    parse_migrations(migrations, config.dialect)

    engine = ReviewEngine()
    bundle = engine.review(migrations, config=config, input_path=str(migrations_path))
    parse_error_count = sum(1 for issue in bundle.issues if issue.rule_id == "safety.parse_error")

    if format in {OutputFormat.TERMINAL, OutputFormat.ALL}:
        render_terminal_report(bundle, report_title=config.report_title, console=console)

    if parse_error_count:
        typer.secho(
            f"Warning: {parse_error_count} statement(s) could not be parsed "
            "and were reported as safety.parse_error.",
            fg=typer.colors.YELLOW,
            err=True,
        )

    generated: list[Path] = []
    if format in {OutputFormat.JSON, OutputFormat.ALL}:
        generated.append(write_json_report(bundle, output_dir=output_dir))
    if format in {OutputFormat.HTML, OutputFormat.ALL}:
        generated.append(write_html_report(bundle, output_dir=output_dir))

    for path in generated:
        typer.secho(f"Generated report: {path}", fg=typer.colors.GREEN)

    if bundle.status == ReviewStatus.FAIL:
        raise typer.Exit(code=1)


@app.command("init-examples")
def init_examples(
    destination: Path = typer.Option(
        Path("examples"),
        "--destination",
        "-d",
        help="Directory where example files will be created.",
    ),
    force: bool = typer.Option(False, "--force", help="Overwrite existing files if they exist."),
) -> None:
    """Initialize example migration and config files."""

    written = write_example_files(destination, overwrite=force)
    if not written:
        typer.secho(
            "No files written. Use --force to overwrite existing examples.",
            fg=typer.colors.YELLOW,
        )
        return

    for path in written:
        typer.secho(f"Created: {path}", fg=typer.colors.GREEN)


@app.command("version")
def version() -> None:
    """Print tool version."""

    typer.echo(__version__)


if __name__ == "__main__":
    app()
