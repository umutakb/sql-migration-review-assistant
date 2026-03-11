from __future__ import annotations

from pathlib import Path

from sql_migration_review_assistant.loader import (
    collect_sql_paths,
    collect_sql_paths_with_strategy,
    load_migration_files,
)


def test_collect_sql_paths_directory_sorted_and_ignored(tmp_path: Path) -> None:
    (tmp_path / "b.sql").write_text("SELECT 1;", encoding="utf-8")
    (tmp_path / "a.sql").write_text("SELECT 1;", encoding="utf-8")
    ignored_dir = tmp_path / "archive"
    ignored_dir.mkdir()
    (ignored_dir / "old.sql").write_text("SELECT 1;", encoding="utf-8")

    paths = collect_sql_paths(tmp_path, ignored_patterns=["archive/*.sql"])

    assert [p.name for p in paths] == ["a.sql", "b.sql"]


def test_collect_sql_paths_single_file(tmp_path: Path) -> None:
    file_path = tmp_path / "001_init.sql"
    file_path.write_text("SELECT 1;", encoding="utf-8")

    paths = collect_sql_paths(file_path)

    assert paths == [file_path.resolve()]


def test_load_migration_files_relative_paths(tmp_path: Path) -> None:
    sub = tmp_path / "migrations"
    sub.mkdir()
    file_path = sub / "001.sql"
    file_path.write_text("SELECT 1;", encoding="utf-8")

    migrations = load_migration_files([file_path], root=sub)

    assert len(migrations) == 1
    assert migrations[0].relative_path == "001.sql"
    assert "SELECT 1" in migrations[0].content


def test_collect_sql_paths_numeric_strategy(tmp_path: Path) -> None:
    (tmp_path / "10_later.sql").write_text("SELECT 1;", encoding="utf-8")
    (tmp_path / "2_earlier.sql").write_text("SELECT 1;", encoding="utf-8")

    paths, strategy = collect_sql_paths_with_strategy(tmp_path)

    assert strategy == "numeric-prefix"
    assert [p.name for p in paths] == ["2_earlier.sql", "10_later.sql"]


def test_collect_sql_paths_timestamp_strategy(tmp_path: Path) -> None:
    (tmp_path / "20260101121000_add.sql").write_text("SELECT 1;", encoding="utf-8")
    (tmp_path / "20260101120000_create.sql").write_text("SELECT 1;", encoding="utf-8")

    paths, strategy = collect_sql_paths_with_strategy(tmp_path)

    assert strategy == "timestamp"
    assert [p.name for p in paths] == ["20260101120000_create.sql", "20260101121000_add.sql"]


def test_collect_sql_paths_fallback_lexicographic(tmp_path: Path) -> None:
    (tmp_path / "zeta.sql").write_text("SELECT 1;", encoding="utf-8")
    (tmp_path / "alpha.sql").write_text("SELECT 1;", encoding="utf-8")
    (tmp_path / "20260101_mixed.sql").write_text("SELECT 1;", encoding="utf-8")

    paths, strategy = collect_sql_paths_with_strategy(tmp_path)

    assert strategy == "lexicographic"
    assert [p.name for p in paths] == ["20260101_mixed.sql", "alpha.sql", "zeta.sql"]
