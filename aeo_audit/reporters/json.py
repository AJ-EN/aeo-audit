"""JSON reporter - machine-readable output for CI/CD integration."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from aeo_audit.core.models import ScanResult


class JsonReporter:
    """Serializes scan results to JSON."""

    def render(self, result: ScanResult, compact: bool = False) -> str:
        """Render scan result as JSON string."""
        # Start with the scorecard dump
        data = result.scorecard.model_dump(mode="json", exclude_none=True)

        # Extract timings per check
        check_timings = {c.name: c.duration_ms for c in result.check_results}

        # Build scan_metadata
        cache_stats = result.raw_data.get("cache_stats", {"hits": 0, "misses": 0})
        crawler_stats = result.raw_data.get(
            "crawler_stats",
            {
                "pages_crawled": 1,
                "bytes_transferred": len(result.raw_data.get("rendered_html", "")),
            },
        )

        data["scan_metadata"] = {
            "url": result.url,
            "timestamp": result.timestamp.isoformat()
            if hasattr(result.timestamp, "isoformat")
            else str(result.timestamp),
            "duration_ms": result.scorecard.scan_duration_ms,
            "version": result.scan_version,
            "check_timings": check_timings,
            "cache_stats": cache_stats,
            "crawler_stats": crawler_stats,
        }

        if compact:
            return json.dumps(data, separators=(",", ":"))
        return json.dumps(data, indent=2)

    def write(self, result: ScanResult, output_path: Path, compact: bool = False) -> None:
        """Write scan result to JSON file."""
        # Ensure parent directories exist
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(self.render(result, compact=compact), encoding="utf-8")

    def generate(self, result: ScanResult, output_path: Path) -> None:
        """Generate JSON report (alias for write)."""
        self.write(result, output_path)
