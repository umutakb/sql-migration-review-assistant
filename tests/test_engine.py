from __future__ import annotations

from pathlib import Path

from sql_migration_review_assistant.config import load_config
from sql_migration_review_assistant.engine import ReviewEngine
from sql_migration_review_assistant.loader import load_migration_files
from sql_migration_review_assistant.models import Severity
from sql_migration_review_assistant.parser import parse_migrations


def test_engine_reviews_and_builds_bundle(fixture_dir: Path, default_config) -> None:
    paths = [fixture_dir / "risky.sql"]
    migrations = load_migration_files(paths, root=fixture_dir)
    parse_migrations(migrations, "postgres")

    bundle = ReviewEngine().review(migrations, default_config, input_path="fixtures/risky.sql")

    assert bundle.summary.scanned_files == 1
    assert bundle.summary.total_statements == 4
    assert bundle.summary.total_issues > 0
    assert bundle.file_summaries[0].file_path == "risky.sql"


def test_engine_safe_file_has_non_fail_status(fixture_dir: Path, default_config) -> None:
    paths = [fixture_dir / "safe.sql"]
    migrations = load_migration_files(paths, root=fixture_dir)
    parse_migrations(migrations, "postgres")

    bundle = ReviewEngine().review(migrations, default_config, input_path="fixtures/safe.sql")

    assert bundle.status.value in {"pass", "warning"}


def test_engine_applies_severity_override(fixture_dir: Path) -> None:
    paths = [fixture_dir / "destructive.sql"]
    migrations = load_migration_files(paths, root=fixture_dir)
    parse_migrations(migrations, "postgres")

    config = load_config(None)
    config.severity_overrides["destructive.drop_table"] = Severity.INFO
    bundle = ReviewEngine().review(migrations, config, input_path="fixtures/destructive.sql")

    issue = next(item for item in bundle.issues if item.rule_id == "destructive.drop_table")
    assert issue.severity == Severity.INFO
