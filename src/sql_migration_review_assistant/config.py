"""Configuration loading utilities."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

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


def _coerce_bool(value: Any, key: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float) and value in {0, 1}:
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    raise ValueError(f"Invalid boolean for '{key}': {value!r}. Use true/false.")


def _coerce_severity(value: Any, key: str) -> Severity:
    if isinstance(value, Severity):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        try:
            return Severity(normalized)
        except ValueError as exc:
            allowed = ", ".join(item.value for item in Severity)
            raise ValueError(
                f"Invalid severity for '{key}': {value!r}. Allowed: {allowed}."
            ) from exc

    raise ValueError(f"Invalid severity for '{key}': {value!r}.")


def _coerce_rule_states(raw: dict[str, Any], key: str) -> dict[str, bool]:
    states: dict[str, bool] = {}
    for rule_id, value in raw.items():
        states[str(rule_id)] = _coerce_bool(value, f"{key}.{rule_id}")
    return states


def _coerce_severity_overrides(raw: dict[str, Any]) -> dict[str, Severity]:
    overrides: dict[str, Severity] = {}
    for rule_id, value in raw.items():
        overrides[str(rule_id)] = _coerce_severity(value, f"severity_mapping.{rule_id}")
    return overrides


def _coerce_fail_threshold(raw: Any) -> dict[str, Any]:
    if isinstance(raw, str | Severity):
        severity = _coerce_severity(raw, "fail_threshold.severity")
        return {"severity": severity.value, "risk_score": 25.0}

    if not isinstance(raw, dict):
        raise ValueError("Invalid 'fail_threshold'. Expected mapping with severity and risk_score.")

    severity = _coerce_severity(
        raw.get("severity", Severity.ERROR.value), "fail_threshold.severity"
    )
    risk_score_raw = raw.get("risk_score", 25.0)
    try:
        risk_score = float(risk_score_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Invalid fail_threshold.risk_score: {risk_score_raw!r}. Must be a number."
        ) from exc

    if risk_score < 0:
        raise ValueError("fail_threshold.risk_score cannot be negative.")

    return {"severity": severity.value, "risk_score": risk_score}


def _coerce_path_patterns(raw: Any, key: str) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError(f"Invalid '{key}'. Expected a list of glob patterns.")
    return [str(item) for item in raw if str(item).strip()]


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

    try:
        with path.open("r", encoding="utf-8") as handle:
            raw = yaml.safe_load(handle) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"Failed to parse YAML config '{path}': {exc}") from exc

    if not isinstance(raw, dict):
        raise ValueError("Config YAML must define a mapping at the root level.")

    if "report_title" in raw:
        merged["report_title"] = str(raw["report_title"])

    if "dialect" in raw:
        merged["dialect"] = str(raw["dialect"])

    enabled_rules = raw.get("enabled_rules") or raw.get("rules")
    if isinstance(enabled_rules, dict):
        merged["enabled_rules"].update(_coerce_rule_states(enabled_rules, "enabled_rules"))

    disabled_rules = raw.get("disabled_rules")
    if disabled_rules is not None:
        if not isinstance(disabled_rules, list):
            raise ValueError("Invalid 'disabled_rules'. Expected a list of rule IDs.")
        for rule_id in disabled_rules:
            merged["enabled_rules"][str(rule_id)] = False

    severity_raw = raw.get("severity_mapping") or raw.get("severity_overrides")
    if isinstance(severity_raw, dict):
        merged["severity_overrides"] = _coerce_severity_overrides(severity_raw)

    if isinstance(raw.get("risk_weights"), dict):
        merged["risk_weights"].update({k: float(v) for k, v in raw["risk_weights"].items()})

    if "fail_on" in raw and "fail_threshold" not in raw:
        merged["fail_threshold"]["severity"] = _coerce_severity(raw["fail_on"], "fail_on").value

    if "fail_threshold" in raw:
        merged["fail_threshold"] = _coerce_fail_threshold(raw["fail_threshold"])

    ignore_keys = ("ignored_paths", "ignored_patterns", "ignore_paths", "exclude_patterns")
    collected_patterns: list[str] = []
    for key in ignore_keys:
        collected_patterns.extend(_coerce_path_patterns(raw.get(key), key))

    if collected_patterns:
        # Preserve order and remove duplicates.
        merged["ignored_paths"] = list(dict.fromkeys(collected_patterns))

    try:
        return ToolConfig(**merged)
    except ValidationError as exc:
        raise ValueError(f"Invalid config values in '{path}': {exc}") from exc
