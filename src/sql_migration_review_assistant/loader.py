"""Input loading utilities for migration files."""

from __future__ import annotations

import re
from fnmatch import fnmatch
from pathlib import Path
from typing import Literal

from .models import MigrationFile

OrderStrategy = Literal["single-file", "numeric-prefix", "timestamp", "lexicographic"]


def _relative_key(path: Path, base: Path) -> str:
    return path.resolve().relative_to(base).as_posix()


def _numeric_prefix(path: Path) -> int | None:
    match = re.match(r"^(\d+)", path.stem)
    if not match:
        return None
    return int(match.group(1))


def _timestamp_key(path: Path) -> int | None:
    # Supports: 20260101_x.sql, 20260101123000_x.sql, 2026-01-01_x.sql variants.
    match = re.match(r"^(\d{4}[-_]?\d{2}[-_]?\d{2}(?:[-_]?\d{2}[-_]?\d{2}[-_]?\d{2})?)", path.stem)
    if not match:
        return None
    normalized = re.sub(r"[-_]", "", match.group(1))
    if len(normalized) not in {8, 14}:
        return None
    return int(normalized)


def _is_ignored(path: Path, base: Path, ignored_patterns: list[str]) -> bool:
    relative = path.relative_to(base).as_posix()
    return any(
        fnmatch(relative, pattern) or fnmatch(path.name, pattern) for pattern in ignored_patterns
    )


def collect_sql_paths_with_strategy(
    input_path: Path, ignored_patterns: list[str] | None = None
) -> tuple[list[Path], OrderStrategy]:
    """Collect and sort SQL paths plus ordering strategy metadata."""

    if not input_path.exists():
        raise FileNotFoundError(f"Input path not found: {input_path}")

    ignored_patterns = ignored_patterns or []

    if input_path.is_file():
        if input_path.suffix.lower() != ".sql":
            raise ValueError(f"Input file must be a .sql file: {input_path}")
        return [input_path.resolve()], "single-file"

    base = input_path.resolve()
    sql_paths = [
        path
        for path in base.rglob("*.sql")
        if path.is_file() and not _is_ignored(path.resolve(), base, ignored_patterns)
    ]
    resolved = sorted(path.resolve() for path in sql_paths)

    if not resolved:
        return [], "lexicographic"

    timestamp_map = {path: _timestamp_key(path) for path in resolved}
    if all(key is not None for key in timestamp_map.values()):
        ordered = sorted(
            resolved,
            key=lambda path: (int(timestamp_map[path] or 0), _relative_key(path, base)),
        )
        return ordered, "timestamp"

    numeric_map = {path: _numeric_prefix(path) for path in resolved}
    if all(key is not None for key in numeric_map.values()):
        ordered = sorted(
            resolved,
            key=lambda path: (int(numeric_map[path] or 0), _relative_key(path, base)),
        )
        return ordered, "numeric-prefix"

    ordered = sorted(resolved, key=lambda path: _relative_key(path, base))
    return ordered, "lexicographic"


def collect_sql_paths(input_path: Path, ignored_patterns: list[str] | None = None) -> list[Path]:
    """Collect and sort SQL file paths from file or directory input."""

    paths, _ = collect_sql_paths_with_strategy(input_path, ignored_patterns=ignored_patterns)
    return paths


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
