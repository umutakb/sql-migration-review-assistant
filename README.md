# sql-migration-review-assistant

Production-grade, PostgreSQL-focused CLI tool for reviewing SQL migration files and surfacing risky changes before deploy.

`sql-migration-review-assistant` scans migration SQL, applies configurable risk rules, and produces:

- terminal summary (Rich)
- machine-readable JSON report
- static HTML report (Jinja2)

## Why This Project

SQL migrations are one of the most common sources of production incidents:

- destructive statements (`DROP`, `TRUNCATE`, `DELETE` without `WHERE`)
- locking/rewrite-heavy schema changes
- missing safety hygiene (rollback notes, transaction pitfalls)
- hard-to-review raw data mutations

This tool adds a repeatable review gate for migration PRs and CI pipelines.

## PostgreSQL Focus

First version is intentionally PostgreSQL-oriented:

- PostgreSQL-safe heuristics (`CREATE INDEX CONCURRENTLY`, transaction constraints)
- `dialect: postgres` default
- SQL parsing done with `sqlglot` using PostgreSQL dialect

## Features

- CLI commands:
  - `smra review <migrations_path>`
  - `smra review <single_file.sql>`
  - `smra review <path> --format all --output-dir ./artifacts`
  - `smra review <path> --fail-on error`
  - `smra init-examples`
  - `smra version`
- Inputs:
  - single `.sql` file
  - directory containing `.sql` files (sorted scan)
  - ignored path patterns via config
- Rule engine:
  - modular rule classes
  - config-driven enable/disable and severity overrides
- Risk model:
  - severity (`error`, `warning`, `info`)
  - per-issue risk weight
  - file-level risk summaries
  - final status (`pass`, `warning`, `fail`)
- Reports:
  - Rich terminal output
  - JSON report bundle
  - static HTML report with summary cards and findings table

## Installation

```bash
pip install -e '.[dev]'
```

## Quick Start

```bash
smra version
smra review examples/risky_migration.sql
smra review examples/ --format all --output-dir artifacts
smra init-examples
```

## CLI Usage

```bash
smra review PATH [OPTIONS]
```

Common options:

- `--format [terminal|json|html|all]`
- `--output-dir PATH` (default: `artifacts`)
- `--config PATH` (default: uses `./config.yaml` if exists)
- `--fail-on [error|warning|info]`

Behavior:

- non-zero exit (`1`) when final status is `fail`
- parse failures are reported as issues (`safety.parse_error`)

## Configuration (`config.yaml`)

```yaml
report_title: SQL Migration Review Report

dialect: postgres

enabled_rules:
  destructive.drop_table: true
  performance.create_index_without_concurrently: true
  safety.rollback_comment_missing: true

severity_mapping:
  safety.transaction_safety: warning
  schema.rename_drop_add_heuristic: info

fail_threshold:
  severity: error
  risk_score: 25

risk_weights:
  severity.error: 8
  severity.warning: 3
  severity.info: 1
  destructive.drop_table: 12

ignored_paths:
  - archive/*.sql
  - legacy/**/*.sql
```

## Rule Families

### A) Destructive Rules

- `destructive.drop_table`
- `destructive.drop_column`
- `destructive.truncate`
- `destructive.delete_without_where`
- `destructive.irreversible_operation`

### B) Schema Change Rules

- `schema.alter_column_type`
- `schema.nullable_to_not_null`
- `schema.not_null_without_default`
- `schema.enum_or_type_narrowing`
- `schema.rename_drop_add_heuristic`

### C) Performance / Locking Rules

- `performance.missing_index_for_foreign_key`
- `performance.large_table_mutation`
- `performance.create_index_without_concurrently`
- `performance.table_rewrite_risk`

### D) Safety / Review Hygiene Rules

- `safety.rollback_comment_missing`
- `safety.description_comment_missing`
- `safety.transaction_safety`
- `safety.raw_update_delete`
- `safety.parse_error`

## Reports

### Terminal Summary (Rich)

Includes:

- scanned files
- total statements
- issue counts by severity
- total risk score
- final status
- top risky files
- top findings

Example (shortened):

```text
SQL Migration Review Report
Scanned Files: 1
Total Statements: 4
Total Issues: 8
Errors: 1, Warnings: 5, Info: 2
Total Risk Score: 33.00
Status: FAIL
```

### JSON Report

`smra-report.json` contains:

- `tool_version`
- `generated_at`
- `input_path`
- `scanned_files`
- `summary`
- `file_summaries`
- `issues`
- `status`

### HTML Report

`smra-report.html` contains:

- header + metadata
- summary cards
- severity breakdown
- risk score
- file risk summary table
- detailed findings table
- generation timestamp

## Project Structure

```text
sql-migration-review-assistant/
  src/sql_migration_review_assistant/
    __init__.py
    cli.py
    config.py
    models.py
    loader.py
    parser.py
    engine.py
    scoring.py
    utils.py
    example_data.py
    rules/
      __init__.py
      base.py
      destructive.py
      schema_changes.py
      performance.py
      safety.py
    reporters/
      __init__.py
      terminal.py
      json_reporter.py
      html_reporter.py
    templates/
      report.html.j2
  tests/
    fixtures/
    conftest.py
    test_loader.py
    test_parser.py
    test_engine.py
    test_scoring.py
    test_rules_destructive.py
    test_rules_schema_changes.py
    test_rules_performance.py
    test_rules_safety.py
    test_reporters.py
    test_cli.py
  examples/
    safe_migration.sql
    risky_migration.sql
    destructive_migration.sql
    config.yaml
  .github/workflows/ci.yml
  README.md
  pyproject.toml
  Makefile
  LICENSE
```

## Development

```bash
make install
make lint
make test
```

CI runs:

- `ruff check .`
- `black --check .`
- `pytest`

## Example Migrations Included

- `examples/safe_migration.sql`
- `examples/risky_migration.sql`
- `examples/destructive_migration.sql`
- `examples/config.yaml`

Also bootstrap examples into your current folder:

```bash
smra init-examples
```

## Roadmap

- rule packs for MySQL/SQLite dialects
- suppression annotations and baseline files
- SARIF export for code scanning platforms
- richer SQL metadata for cross-file dependency checks
- optional mypy in CI (strict mode)

## License

MIT
