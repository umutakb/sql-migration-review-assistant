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
    help="SQL migration review assistant for risk detection and reporting.",
)
console = Console()


class OutputFormat(StrEnum):
    TERMINAL = "terminal"
    JSON = "json"
    HTML = "html"
    ALL = "all"


@app.command("review")
def review(
    migrations_path: Path = typer.Argument(
        ..., help="SQL file or directory containing .sql files."
    ),
    format: OutputFormat = typer.Option(
        OutputFormat.TERMINAL,
        "--format",
        "-f",
        help="Output format: terminal, json, html, or all.",
        case_sensitive=False,
    ),
    output_dir: Path = typer.Option(
        Path("artifacts"),
        "--output-dir",
        "-o",
        help="Output directory for generated reports.",
    ),
    config_path: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to config.yaml. Defaults to ./config.yaml if present.",
    ),
    fail_on: Severity | None = typer.Option(
        None,
        "--fail-on",
        help="Fail threshold override: error | warning | info.",
        case_sensitive=False,
    ),
) -> None:
    """Analyze SQL migrations and generate risk findings."""

    try:
        config = load_config(config_path)
    except (FileNotFoundError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    if fail_on is not None:
        config.fail_threshold.severity = fail_on

    try:
        sql_paths = collect_sql_paths(migrations_path, config.ignored_paths)
    except (FileNotFoundError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    if not sql_paths:
        typer.secho("No SQL files found for analysis.", fg=typer.colors.YELLOW)
        raise typer.Exit(code=1)

    root = migrations_path if migrations_path.is_dir() else migrations_path.parent
    migrations = load_migration_files(sql_paths, root=root)
    parse_migrations(migrations, config.dialect)

    engine = ReviewEngine()
    bundle = engine.review(migrations, config=config, input_path=str(migrations_path))

    if format in {OutputFormat.TERMINAL, OutputFormat.ALL}:
        render_terminal_report(bundle, report_title=config.report_title, console=console)

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
