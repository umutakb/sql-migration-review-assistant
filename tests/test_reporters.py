from __future__ import annotations

import json
from pathlib import Path

from sql_migration_review_assistant.engine import ReviewEngine
from sql_migration_review_assistant.loader import load_migration_files
from sql_migration_review_assistant.parser import parse_migrations
from sql_migration_review_assistant.reporters.html_reporter import write_html_report
from sql_migration_review_assistant.reporters.json_reporter import write_json_report


def _bundle_from_fixture(fixture_dir: Path, default_config):
    paths = [fixture_dir / "risky.sql"]
    migrations = load_migration_files(paths, root=fixture_dir)
    parse_migrations(migrations, "postgres")
    return ReviewEngine().review(migrations, default_config, input_path="fixtures/risky.sql")


def test_json_report_generation(tmp_path: Path, fixture_dir: Path, default_config) -> None:
    bundle = _bundle_from_fixture(fixture_dir, default_config)

    report_path = write_json_report(bundle, tmp_path)

    assert report_path.exists()
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["summary"]["total_issues"] >= 1
    assert payload["tool_version"]


def test_html_report_generation(tmp_path: Path, fixture_dir: Path, default_config) -> None:
    bundle = _bundle_from_fixture(fixture_dir, default_config)

    report_path = write_html_report(bundle, tmp_path)

    html = report_path.read_text(encoding="utf-8")
    assert "SQL Migration Review Report" in html
    assert "Detailed Findings" in html
