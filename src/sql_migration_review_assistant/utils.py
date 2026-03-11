"""Generic helpers used across modules."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from .example_data import EXAMPLE_FILES


def utc_now() -> datetime:
    """Return timezone-aware UTC datetime."""

    return datetime.now(UTC)


def sql_excerpt(sql: str, max_len: int = 120) -> str:
    """Return compact statement excerpt for reports."""

    compact = " ".join(sql.strip().split())
    if len(compact) <= max_len:
        return compact
    return f"{compact[: max_len - 3]}..."


def write_example_files(destination: Path, overwrite: bool = False) -> list[Path]:
    """Create packaged example files under destination directory."""

    destination.mkdir(parents=True, exist_ok=True)
    written_paths: list[Path] = []

    for name, content in EXAMPLE_FILES.items():
        target = destination / name
        if target.exists() and not overwrite:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        written_paths.append(target)

    return written_paths
