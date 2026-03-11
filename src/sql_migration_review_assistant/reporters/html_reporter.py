"""HTML report writer using Jinja2 template."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

from ..models import ReportBundle


def _environment() -> Environment:
    return Environment(
        loader=PackageLoader("sql_migration_review_assistant", "templates"),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def write_html_report(
    bundle: ReportBundle, output_dir: Path, filename: str = "smra-report.html"
) -> Path:
    """Render static HTML report from bundle."""

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename

    template = _environment().get_template("report.html.j2")
    html = template.render(bundle=bundle)
    output_path.write_text(html, encoding="utf-8")
    return output_path
