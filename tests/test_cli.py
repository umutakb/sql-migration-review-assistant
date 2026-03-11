from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from sql_migration_review_assistant.cli import app

runner = CliRunner()


def test_cli_version() -> None:
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert result.stdout.strip()


def test_cli_init_examples(tmp_path: Path) -> None:
    destination = tmp_path / "examples"

    result = runner.invoke(app, ["init-examples", "--destination", str(destination)])

    assert result.exit_code == 0
    assert (destination / "safe_migration.sql").exists()
    assert (destination / "config.yaml").exists()


def test_cli_review_single_file_outputs_json(tmp_path: Path, fixture_dir: Path) -> None:
    output_dir = tmp_path / "artifacts"
    sql_file = fixture_dir / "risky.sql"

    result = runner.invoke(
        app,
        [
            "review",
            str(sql_file),
            "--format",
            "json",
            "--output-dir",
            str(output_dir),
            "--fail-on",
            "info",
        ],
    )

    assert result.exit_code == 1
    assert (output_dir / "smra-report.json").exists()
