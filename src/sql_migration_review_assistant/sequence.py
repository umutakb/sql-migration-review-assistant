"""Sequence-level heuristic analysis for ordered migrations."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from .models import (
    MigrationFile,
    MigrationSequenceSummary,
    SequenceInsight,
    Severity,
    StatementInfo,
)

_IDENTIFIER = r"[A-Za-z_\"\.][A-Za-z0-9_\"\.]*"
_DROP_COL_RE = re.compile(
    rf"ALTER\s+TABLE\s+({_IDENTIFIER}).*?DROP\s+COLUMN\s+({_IDENTIFIER})",
    re.IGNORECASE | re.DOTALL,
)
_ADD_COL_RE = re.compile(
    rf"ALTER\s+TABLE\s+({_IDENTIFIER}).*?ADD\s+COLUMN\s+({_IDENTIFIER})",
    re.IGNORECASE | re.DOTALL,
)
_CREATE_TABLE_RE = re.compile(
    rf"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?({_IDENTIFIER})",
    re.IGNORECASE,
)
_CREATE_INDEX_RE = re.compile(
    rf"CREATE\s+(?:UNIQUE\s+)?INDEX(?:\s+CONCURRENTLY)?\s+{_IDENTIFIER}\s+ON\s+({_IDENTIFIER})",
    re.IGNORECASE,
)
_TOUCH_SQL_RE = re.compile(
    r"^(ALTER\s+TABLE|UPDATE\b|DELETE\b|DROP\s+TABLE|TRUNCATE\b)",
    re.IGNORECASE,
)
_PROTECTIVE_SQL_RE = re.compile(
    r"(RENAME\s+COLUMN|ADD\s+COLUMN|UPDATE\b.*\bWHERE\b|CREATE\s+TABLE|INSERT\s+INTO|BACKFILL)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class _ColumnEvent:
    index: int
    file_path: str
    table: str
    column: str


@dataclass(frozen=True)
class _TableEvent:
    index: int
    file_path: str
    table: str


@dataclass(frozen=True)
class _DestructiveEvent:
    index: int
    file_path: str
    table: str | None


def _normalize_identifier(value: str) -> str:
    return value.strip().strip('"').lower()


def _statement_sql(statement: StatementInfo) -> str:
    return " ".join(statement.raw_sql.strip().split())


def _extract_column_events(
    files: list[MigrationFile],
) -> tuple[list[_ColumnEvent], list[_ColumnEvent]]:
    drop_events: list[_ColumnEvent] = []
    add_events: list[_ColumnEvent] = []

    for index, file in enumerate(files):
        for statement in file.statements:
            drop_match = _DROP_COL_RE.search(statement.raw_sql)
            if drop_match:
                drop_events.append(
                    _ColumnEvent(
                        index=index,
                        file_path=file.relative_path,
                        table=_normalize_identifier(drop_match.group(1)),
                        column=_normalize_identifier(drop_match.group(2)),
                    )
                )

            add_match = _ADD_COL_RE.search(statement.raw_sql)
            if add_match:
                add_events.append(
                    _ColumnEvent(
                        index=index,
                        file_path=file.relative_path,
                        table=_normalize_identifier(add_match.group(1)),
                        column=_normalize_identifier(add_match.group(2)),
                    )
                )

    return drop_events, add_events


def _extract_create_events(
    files: list[MigrationFile],
) -> tuple[list[_TableEvent], list[_TableEvent]]:
    create_tables: list[_TableEvent] = []
    create_indexes: list[_TableEvent] = []

    for index, file in enumerate(files):
        for statement in file.statements:
            create_match = _CREATE_TABLE_RE.search(statement.raw_sql)
            if create_match:
                create_tables.append(
                    _TableEvent(
                        index=index,
                        file_path=file.relative_path,
                        table=_normalize_identifier(create_match.group(1)),
                    )
                )

            index_match = _CREATE_INDEX_RE.search(statement.raw_sql)
            if index_match:
                create_indexes.append(
                    _TableEvent(
                        index=index,
                        file_path=file.relative_path,
                        table=_normalize_identifier(index_match.group(1)),
                    )
                )

    return create_tables, create_indexes


def _extract_destructive_events(files: list[MigrationFile]) -> list[_DestructiveEvent]:
    destructive_events: list[_DestructiveEvent] = []

    for index, file in enumerate(files):
        for statement in file.statements:
            sql = _statement_sql(statement).upper()
            if not (
                sql.startswith("DROP TABLE")
                or sql.startswith("TRUNCATE")
                or sql.startswith("DELETE")
            ):
                continue

            table: str | None = None
            if statement.table_names:
                table = _normalize_identifier(statement.table_names[0])

            destructive_events.append(
                _DestructiveEvent(index=index, file_path=file.relative_path, table=table)
            )

    return destructive_events


def _extract_touch_map(files: list[MigrationFile]) -> dict[str, list[tuple[int, str]]]:
    touch_map: dict[str, list[tuple[int, str]]] = defaultdict(list)

    for index, file in enumerate(files):
        for statement in file.statements:
            if not _TOUCH_SQL_RE.search(_statement_sql(statement)):
                continue
            for table in statement.table_names:
                touch_map[_normalize_identifier(table)].append((index, file.relative_path))

    return touch_map


def _has_protective_followup(
    files: list[MigrationFile], start_index: int, table: str | None
) -> bool:
    followup_indices = range(start_index + 1, min(start_index + 3, len(files)))

    for idx in followup_indices:
        file = files[idx]
        for statement in file.statements:
            sql = _statement_sql(statement)
            if not _PROTECTIVE_SQL_RE.search(sql):
                continue
            if table is None:
                return True
            if table in {_normalize_identifier(name) for name in statement.table_names}:
                return True
            if table in sql.lower():
                return True

    return False


def _filename_kind(path: str) -> str:
    stem = Path(path).stem
    if re.match(r"^\d{8}(?:\d{6})?", stem):
        return "timestamp"
    if re.match(r"^\d+", stem):
        return "numeric"
    return "plain"


def _ordering_insights(files: list[MigrationFile], ordering_strategy: str) -> list[SequenceInsight]:
    insights: list[SequenceInsight] = []
    file_names = [file.relative_path for file in files]
    kinds = {_filename_kind(path) for path in file_names}

    if ordering_strategy == "lexicographic" and len(kinds) > 1:
        insights.append(
            SequenceInsight(
                kind="suspicious_ordering",
                severity=Severity.WARNING,
                message=(
                    "Migration filenames use mixed patterns (numeric/timestamp/plain). "
                    "Consider a consistent naming scheme for predictable ordering."
                ),
                related_files=file_names[:8],
                confidence=0.72,
            )
        )

    if ordering_strategy == "numeric-prefix":
        prefixes: dict[str, list[str]] = defaultdict(list)
        for path in file_names:
            match = re.match(r"^(\d+)", Path(path).stem)
            if match:
                prefixes[match.group(1)].append(path)
        duplicated = [files for files in prefixes.values() if len(files) > 1]
        if duplicated:
            flat = [path for group in duplicated for path in group]
            insights.append(
                SequenceInsight(
                    kind="suspicious_ordering",
                    severity=Severity.INFO,
                    message=(
                        "Multiple migrations share the same numeric prefix. "
                        "Execution order may rely on filename suffixes."
                    ),
                    related_files=flat[:8],
                    confidence=0.66,
                )
            )

    if ordering_strategy == "timestamp":
        timestamp_seen: dict[str, list[str]] = defaultdict(list)
        for path in file_names:
            normalized = re.sub(r"[^0-9]", "", Path(path).stem)
            timestamp_seen[normalized[:14]].append(path)
        collisions = [group for group in timestamp_seen.values() if len(group) > 1]
        if collisions:
            flat = [path for group in collisions for path in group]
            insights.append(
                SequenceInsight(
                    kind="suspicious_ordering",
                    severity=Severity.INFO,
                    message=(
                        "Timestamp-like migration names contain collisions. "
                        "Ordering is still deterministic but potentially ambiguous."
                    ),
                    related_files=flat[:8],
                    confidence=0.61,
                )
            )

    return insights


def analyze_sequence(
    files: list[MigrationFile],
    ordering_strategy: str,
) -> tuple[MigrationSequenceSummary, list[SequenceInsight]]:
    """Build sequence-level insights across ordered migration files."""

    ordered_files = [file.relative_path for file in files]

    if len(files) <= 1:
        summary = MigrationSequenceSummary(
            enabled=False,
            ordering_strategy=ordering_strategy,
            total_files=len(files),
            touched_tables=0,
            insight_count=0,
            warning_count=0,
            info_count=0,
            ordered_files=ordered_files,
        )
        return summary, []

    insights: list[SequenceInsight] = []

    drop_events, add_events = _extract_column_events(files)
    create_events, index_events = _extract_create_events(files)
    destructive_events = _extract_destructive_events(files)
    touch_map = _extract_touch_map(files)

    # A. Potential rename suspicion across adjacent migrations.
    for dropped in drop_events:
        for added in add_events:
            if added.index <= dropped.index or added.index > dropped.index + 2:
                continue
            if added.table != dropped.table:
                continue
            if added.column == dropped.column:
                continue

            similarity = SequenceMatcher(None, dropped.column, added.column).ratio()
            if similarity < 0.45:
                continue

            insights.append(
                SequenceInsight(
                    kind="rename_suspicion",
                    severity=Severity.INFO,
                    message=(
                        f"Column '{dropped.column}' was dropped and '{added.column}' was added "
                        f"on table '{dropped.table}' in nearby migrations. "
                        "This may be a rename implemented as drop+add."
                    ),
                    related_files=[dropped.file_path, added.file_path],
                    related_tables=[dropped.table],
                    confidence=round(min(0.9, max(0.45, similarity)), 2),
                )
            )

    # B. Create-then-index follow-up check.
    for created in create_events:
        has_followup_index = any(
            event.table == created.table and created.index < event.index <= created.index + 2
            for event in index_events
        )
        has_same_file_index = any(
            event.table == created.table and event.index == created.index for event in index_events
        )
        if has_followup_index or has_same_file_index:
            continue

        insights.append(
            SequenceInsight(
                kind="create_then_index",
                severity=Severity.INFO,
                message=(
                    f"Table '{created.table}' is created but no index creation was observed in the "
                    "next migrations. Validate read/query patterns."
                ),
                related_files=[created.file_path],
                related_tables=[created.table],
                confidence=0.58,
            )
        )

    # C. Repeated table touches in a short chain.
    for table, touches in sorted(touch_map.items()):
        touches_sorted = sorted(touches)
        for start in range(len(touches_sorted)):
            window: list[tuple[int, str]] = [touches_sorted[start]]
            for candidate in touches_sorted[start + 1 :]:
                if candidate[0] - window[0][0] <= 2:
                    window.append(candidate)
                else:
                    break
            if len(window) < 3:
                continue

            related_files = list(dict.fromkeys(path for _, path in window))
            insights.append(
                SequenceInsight(
                    kind="repeated_table_touch",
                    severity=Severity.WARNING,
                    message=(
                        f"Table '{table}' is repeatedly modified across nearby migrations. "
                        "Consider batching related changes to reduce deployment churn."
                    ),
                    related_files=related_files,
                    related_tables=[table],
                    confidence=0.74,
                )
            )
            break

    # D. Destructive operation without nearby follow-up safety pattern.
    for event in destructive_events:
        if _has_protective_followup(files, event.index, event.table):
            continue

        table_detail = f" for table '{event.table}'" if event.table else ""
        insights.append(
            SequenceInsight(
                kind="destructive_without_followup",
                severity=Severity.WARNING,
                message=(
                    f"Destructive operation detected{table_detail}, "
                    "but no nearby follow-up pattern "
                    "(rename/backfill/safe-step) was observed in subsequent migrations."
                ),
                related_files=[event.file_path],
                related_tables=[event.table] if event.table else [],
                confidence=0.69,
            )
        )

    # E. Suspicious ordering metadata.
    insights.extend(_ordering_insights(files, ordering_strategy))

    # Deterministic ordering: severity first, then confidence, then kind.
    insights.sort(
        key=lambda item: (
            -item.severity.rank,
            -item.confidence,
            item.kind,
            ",".join(item.related_files),
        )
    )

    touched_tables = len(touch_map)
    warning_count = sum(1 for item in insights if item.severity == Severity.WARNING)
    info_count = sum(1 for item in insights if item.severity == Severity.INFO)

    summary = MigrationSequenceSummary(
        enabled=True,
        ordering_strategy=ordering_strategy,
        total_files=len(files),
        touched_tables=touched_tables,
        insight_count=len(insights),
        warning_count=warning_count,
        info_count=info_count,
        ordered_files=ordered_files,
    )

    return summary, insights
