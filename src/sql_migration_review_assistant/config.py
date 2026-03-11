"""Configuration loading utilities."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .models import Severity, ToolConfig

DEFAULT_ENABLED_RULES: dict[str, bool] = {
    "destructive.drop_table": True,
    "destructive.drop_column": True,
    "destructive.truncate": True,
    "destructive.delete_without_where": True,
    "destructive.irreversible_operation": True,
    "schema.alter_column_type": True,
    "schema.nullable_to_not_null": True,
    "schema.not_null_without_default": True,
    "schema.enum_or_type_narrowing": True,
    "schema.rename_drop_add_heuristic": True,
    "performance.missing_index_for_foreign_key": True,
    "performance.large_table_mutation": True,
    "performance.create_index_without_concurrently": True,
    "performance.table_rewrite_risk": True,
    "safety.rollback_comment_missing": True,
    "safety.description_comment_missing": True,
    "safety.transaction_safety": True,
    "safety.raw_update_delete": True,
    "safety.parse_error": True,
}

DEFAULT_RISK_WEIGHTS: dict[str, float] = {
    "severity.error": 8.0,
    "severity.warning": 3.0,
    "severity.info": 1.0,
    "destructive.drop_table": 12.0,
    "destructive.drop_column": 10.0,
    "destructive.truncate": 10.0,
    "schema.not_null_without_default": 9.0,
}


def _coerce_severity_overrides(raw: dict[str, Any]) -> dict[str, Severity]:
    overrides: dict[str, Severity] = {}
    for key, value in raw.items():
        if isinstance(value, Severity):
            overrides[key] = value
        elif isinstance(value, str):
            overrides[key] = Severity(value.strip().lower())
    return overrides


def load_config(path: Path | None = None) -> ToolConfig:
    """Load tool configuration from YAML, or return defaults when missing."""

    merged: dict[str, Any] = {
        "report_title": "SQL Migration Review Report",
        "dialect": "postgres",
        "enabled_rules": dict(DEFAULT_ENABLED_RULES),
        "severity_overrides": {},
        "risk_weights": dict(DEFAULT_RISK_WEIGHTS),
        "ignored_paths": [],
        "fail_threshold": {"severity": Severity.ERROR.value, "risk_score": 25.0},
    }

    if path is None:
        default_path = Path("config.yaml")
        path = default_path if default_path.exists() else None

    if path is None:
        return ToolConfig(**merged)

    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    if not isinstance(raw, dict):
        raise ValueError("Config YAML must define a mapping at the root level.")

    if "report_title" in raw:
        merged["report_title"] = str(raw["report_title"])

    if "dialect" in raw:
        merged["dialect"] = str(raw["dialect"])

    enabled_rules = raw.get("enabled_rules") or raw.get("rules")
    if isinstance(enabled_rules, dict):
        merged["enabled_rules"].update({k: bool(v) for k, v in enabled_rules.items()})

    severity_raw = raw.get("severity_mapping") or raw.get("severity_overrides")
    if isinstance(severity_raw, dict):
        merged["severity_overrides"] = _coerce_severity_overrides(severity_raw)

    if isinstance(raw.get("risk_weights"), dict):
        merged["risk_weights"].update({k: float(v) for k, v in raw["risk_weights"].items()})

    fail_threshold = raw.get("fail_threshold")
    if isinstance(fail_threshold, dict):
        merged["fail_threshold"] = {
            "severity": str(fail_threshold.get("severity", Severity.ERROR.value)).lower(),
            "risk_score": float(fail_threshold.get("risk_score", 25.0)),
        }

    ignored_paths = raw.get("ignored_paths") or raw.get("ignored_patterns")
    if isinstance(ignored_paths, list):
        merged["ignored_paths"] = [str(item) for item in ignored_paths]

    return ToolConfig(**merged)
