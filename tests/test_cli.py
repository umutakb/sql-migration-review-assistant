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


def test_cli_review_invalid_path_returns_error() -> None:
    result = runner.invoke(app, ["review", "missing/path.sql"])

    assert result.exit_code == 2
    assert "Input path not found" in result.output


def test_cli_review_invalid_config_returns_error(tmp_path: Path, fixture_dir: Path) -> None:
    invalid_config = tmp_path / "bad.yaml"
    invalid_config.write_text(
        "severity_mapping:\n  destructive.drop_table: critical\n", encoding="utf-8"
    )

    result = runner.invoke(
        app,
        ["review", str(fixture_dir / "safe.sql"), "--config", str(invalid_config)],
    )

    assert result.exit_code == 2
    assert "Invalid severity" in result.output


def test_cli_review_parse_failure_prints_warning(fixture_dir: Path) -> None:
    invalid_sql = fixture_dir / "invalid.sql"
    result = runner.invoke(app, ["review", str(invalid_sql)])

    assert result.exit_code == 1
    assert "could not be parsed" in result.output
