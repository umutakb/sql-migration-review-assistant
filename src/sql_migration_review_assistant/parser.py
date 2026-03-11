"""SQL parsing utilities backed by sqlglot."""

from __future__ import annotations

import re
from collections.abc import Iterable

from sqlglot import exp, parse_one
from sqlglot.errors import ParseError

from .models import MigrationFile, StatementInfo

_DOLLAR_TAG_RE = re.compile(r"\$[A-Za-z0-9_]*\$")


def split_sql_statements(sql: str) -> list[str]:
    """Split SQL script into statements while respecting quotes/comments."""

    statements: list[str] = []
    current: list[str] = []

    in_single = False
    in_double = False
    in_line_comment = False
    in_block_comment = False
    dollar_tag: str | None = None

    i = 0
    while i < len(sql):
        ch = sql[i]
        nxt = sql[i + 1] if i + 1 < len(sql) else ""

        if in_line_comment:
            current.append(ch)
            if ch == "\n":
                in_line_comment = False
            i += 1
            continue

        if in_block_comment:
            current.append(ch)
            if ch == "*" and nxt == "/":
                current.append(nxt)
                in_block_comment = False
                i += 2
                continue
            i += 1
            continue

        if dollar_tag is not None:
            if sql.startswith(dollar_tag, i):
                current.append(dollar_tag)
                i += len(dollar_tag)
                dollar_tag = None
                continue
            current.append(ch)
            i += 1
            continue

        if in_single:
            current.append(ch)
            if ch == "'":
                if nxt == "'":
                    current.append(nxt)
                    i += 2
                    continue
                in_single = False
            i += 1
            continue

        if in_double:
            current.append(ch)
            if ch == '"':
                in_double = False
            i += 1
            continue

        if ch == "-" and nxt == "-":
            current.extend([ch, nxt])
            in_line_comment = True
            i += 2
            continue

        if ch == "/" and nxt == "*":
            current.extend([ch, nxt])
            in_block_comment = True
            i += 2
            continue

        dollar_match = _DOLLAR_TAG_RE.match(sql, i)
        if dollar_match:
            tag = dollar_match.group(0)
            current.append(tag)
            dollar_tag = tag
            i += len(tag)
            continue

        if ch == "'":
            current.append(ch)
            in_single = True
            i += 1
            continue

        if ch == '"':
            current.append(ch)
            in_double = True
            i += 1
            continue

        if ch == ";":
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
            i += 1
            continue

        current.append(ch)
        i += 1

    tail = "".join(current).strip()
    if tail:
        statements.append(tail)

    return statements


def _infer_statement_type(sql: str) -> str:
    match = re.match(r"\s*([A-Za-z]+)", sql)
    if not match:
        return "UNKNOWN"
    return match.group(1).upper()


def _extract_table_names(ast: exp.Expression) -> list[str]:
    names = {table.name for table in ast.find_all(exp.Table) if table.name}
    return sorted(names)


def parse_statement(sql: str, index: int, dialect: str) -> StatementInfo:
    """Parse single SQL statement and return StatementInfo."""

    try:
        ast = parse_one(sql, read=dialect)
        statement_type = ast.key.upper() if ast.key else _infer_statement_type(sql)
        return StatementInfo(
            index=index,
            raw_sql=sql,
            statement_type=statement_type,
            table_names=_extract_table_names(ast),
            parsed=True,
            ast=ast,
        )
    except ParseError as exc:
        return StatementInfo(
            index=index,
            raw_sql=sql,
            statement_type=_infer_statement_type(sql),
            table_names=[],
            parsed=False,
            parse_error=str(exc),
            ast=None,
        )


def parse_migration_file(file: MigrationFile, dialect: str) -> MigrationFile:
    """Parse all statements from a migration file."""

    chunks = split_sql_statements(file.content)
    file.statements = [
        parse_statement(chunk, idx, dialect) for idx, chunk in enumerate(chunks, start=1)
    ]
    return file


def parse_migrations(files: Iterable[MigrationFile], dialect: str) -> list[MigrationFile]:
    """Parse all migration files with selected dialect."""

    parsed_files: list[MigrationFile] = []
    for file in files:
        parsed_files.append(parse_migration_file(file, dialect))
    return parsed_files
