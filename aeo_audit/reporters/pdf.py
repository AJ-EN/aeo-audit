"""PDF reporter - WeasyPrint wrapper for HTML -> PDF conversion."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aeo_audit.reporters.html import HtmlReporter

if TYPE_CHECKING:
    from pathlib import Path

    from aeo_audit.core.models import ScanResult


class PdfReporter:
    """Generates PDF reports via HTML→PDF conversion using WeasyPrint."""

    def __init__(self, template_dir: Path | None = None) -> None:
        self._html_reporter = HtmlReporter(template_dir=template_dir)

    def render(self, result: ScanResult) -> bytes:
        """Render scan result as PDF bytes."""
        rendered_html = self._html_reporter.render(result)
        try:
            from weasyprint import HTML
            from weasyprint.text.fonts import FontConfiguration

            font_config = FontConfiguration()
            html = HTML(string=rendered_html)
            # variant="pdf/ua-1" generates a tagged accessible PDF
            return html.write_pdf(font_config=font_config, variant="pdf/ua-1")  # type: ignore
        except Exception as e:
            raise RuntimeError(f"WeasyPrint PDF rendering failed: {e}") from e

    def write(self, result: ScanResult, output_path: Path) -> None:
        """Write PDF report to file."""
        # Ensure parent directories exist
        output_path.parent.mkdir(parents=True, exist_ok=True)
        pdf_bytes = self.render(result)
        output_path.write_bytes(pdf_bytes)

    def generate(self, result: ScanResult, output_path: Path) -> None:
        """Generate PDF report (alias for write)."""
        self.write(result, output_path)
