from __future__ import annotations

from pathlib import Path

import pytest

from sql_migration_review_assistant.config import load_config
from sql_migration_review_assistant.models import Severity


def _write_config(tmp_path: Path, content: str) -> Path:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(content, encoding="utf-8")
    return config_path


def test_load_config_supports_ignore_and_exclude_aliases(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        """
ignore_paths:
  - legacy/*.sql
exclude_patterns:
  - archive/**/*.sql
ignored_paths:
  - legacy/*.sql
""",
    )

    config = load_config(config_path)

    assert config.ignored_paths == ["legacy/*.sql", "archive/**/*.sql"]


def test_load_config_supports_disabled_rules_and_string_booleans(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        """
enabled_rules:
  safety.parse_error: "false"
disabled_rules:
  - destructive.drop_table
""",
    )

    config = load_config(config_path)

    assert config.enabled_rules["safety.parse_error"] is False
    assert config.enabled_rules["destructive.drop_table"] is False


def test_load_config_applies_severity_override_and_fail_on_alias(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        """
severity_mapping:
  destructive.drop_table: warning
fail_on: warning
""",
    )

    config = load_config(config_path)

    assert config.severity_overrides["destructive.drop_table"] == Severity.WARNING
    assert config.fail_threshold.severity == Severity.WARNING


def test_load_config_invalid_severity_message(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        """
severity_mapping:
  destructive.drop_table: critical
""",
    )

    with pytest.raises(ValueError, match="Invalid severity"):
        load_config(config_path)


def test_load_config_invalid_enabled_rule_boolean_message(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        """
enabled_rules:
  safety.parse_error: maybe
""",
    )

    with pytest.raises(ValueError, match="Invalid boolean"):
        load_config(config_path)


def test_load_config_negative_fail_threshold_rejected(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        """
fail_threshold:
  severity: error
  risk_score: -1
""",
    )

    with pytest.raises(ValueError, match="cannot be negative"):
        load_config(config_path)
