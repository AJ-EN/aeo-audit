"""HTML reporter - Jinja2 template-based client-ready reports."""

from __future__ import annotations

from typing import TYPE_CHECKING

from jinja2 import Environment, FileSystemLoader, PackageLoader

if TYPE_CHECKING:
    from pathlib import Path

    from aeo_audit.core.models import ScanResult


class HtmlReporter:
    """Generates HTML reports from Jinja2 templates.

    Features:
    - Executive summary (score, grade, percentile)
    - Category breakdown with radar chart (Chart.js)
    - Prioritized fix list: Impact x Effort matrix
    - Raw evidence (JSON snippets, headers)
    - 'Certified Agent-Ready' badge if ≥75
    """

    def __init__(self, template_dir: Path | None = None) -> None:
        if template_dir and template_dir.exists():
            self._env = Environment(
                loader=FileSystemLoader(str(template_dir)),
                autoescape=True,
            )
        else:
            self._env = Environment(
                loader=PackageLoader("aeo_audit", "templates"),
                autoescape=True,
            )

    def render(self, result: ScanResult) -> str:
        """Render scan result as HTML string."""
        template = self._env.get_template("report.html.j2")
        return template.render(
            scorecard=result.scorecard,
            check_results=result.check_results,
            scan_metadata={
                "url": result.url,
                "timestamp": result.timestamp,
                "duration_ms": result.scorecard.scan_duration_ms,
                "version": result.scan_version,
            },
        )

    def write(self, result: ScanResult, output_path: Path) -> None:
        """Write HTML report to file."""
        # Ensure parent directories exist
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(self.render(result), encoding="utf-8")

    def generate(self, result: ScanResult, output_path: Path) -> None:
        """Generate HTML report (alias for write)."""
        self.write(result, output_path)
