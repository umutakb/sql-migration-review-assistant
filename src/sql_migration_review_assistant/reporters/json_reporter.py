"""JSON report writer."""

from __future__ import annotations

import json
from pathlib import Path

from ..models import ReportBundle


def write_json_report(
    bundle: ReportBundle, output_dir: Path, filename: str = "smra-report.json"
) -> Path:
    """Write report as JSON file and return output path."""

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename
    payload = bundle.model_dump(mode="json")
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return output_path
