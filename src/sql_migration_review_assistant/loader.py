"""Input loading utilities for migration files."""

from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path

from .models import MigrationFile


def _is_ignored(path: Path, base: Path, ignored_patterns: list[str]) -> bool:
    relative = path.relative_to(base).as_posix()
    return any(
        fnmatch(relative, pattern) or fnmatch(path.name, pattern) for pattern in ignored_patterns
    )


def collect_sql_paths(input_path: Path, ignored_patterns: list[str] | None = None) -> list[Path]:
    """Collect and sort SQL file paths from file or directory input."""

    if not input_path.exists():
        raise FileNotFoundError(f"Input path not found: {input_path}")

    ignored_patterns = ignored_patterns or []

    if input_path.is_file():
        if input_path.suffix.lower() != ".sql":
            raise ValueError(f"Input file must be a .sql file: {input_path}")
        return [input_path.resolve()]

    base = input_path.resolve()
    sql_paths = [
        path
        for path in base.rglob("*.sql")
        if path.is_file() and not _is_ignored(path.resolve(), base, ignored_patterns)
    ]
    return sorted(path.resolve() for path in sql_paths)


def load_migration_files(paths: list[Path], root: Path) -> list[MigrationFile]:
    """Read SQL files into MigrationFile models."""

    root_resolved = root.resolve()
    migrations: list[MigrationFile] = []

    for path in paths:
        content = path.read_text(encoding="utf-8")
        relative_path = path.resolve().relative_to(root_resolved).as_posix()
        migrations.append(
            MigrationFile(
                path=str(path.resolve()),
                relative_path=relative_path,
                content=content,
            )
        )

    return migrations
