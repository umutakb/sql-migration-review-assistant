from __future__ import annotations

from pathlib import Path

import pytest

from sql_migration_review_assistant.config import load_config
from sql_migration_review_assistant.loader import load_migration_files
from sql_migration_review_assistant.parser import parse_migrations


@pytest.fixture
def fixture_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def default_config():
    return load_config(None)


@pytest.fixture
def parsed_safe_file(fixture_dir: Path):
    paths = [fixture_dir / "safe.sql"]
    migrations = load_migration_files(paths, root=fixture_dir)
    return parse_migrations(migrations, "postgres")[0]
