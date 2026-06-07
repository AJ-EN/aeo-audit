"""Integration tests for the report generation system."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json
import pytest

from aeo_audit.core.models import (
    Category,
    CategoryScore,
    CheckResult,
    CheckStatus,
    ConfidenceInterval,
    Finding,
    Grade,
    ScanResult,
    Scorecard,
    Severity,
)
from aeo_audit.reporters import HtmlReporter, JsonReporter, PdfReporter, TerminalReporter


def get_reporter(fmt: str):
    """Retrieve reporter instance by format name."""
    if fmt == "html":
        return HtmlReporter()
    elif fmt == "pdf":
        return PdfReporter()
    elif fmt == "json":
        return JsonReporter()
    elif fmt == "terminal":
        return TerminalReporter()
    else:
        raise ValueError(f"Unknown format: {fmt}")


@pytest.fixture
def perfect_site_scan() -> ScanResult:
    """Mock ScanResult of a perfect site scan producing an overall score of 73."""
    timestamp = datetime.utcnow()
    
    findings = [
        Finding(
            title="Missing /.well-known/agent-manifest.json",
            description="Missing manifest",
            severity=Severity.HIGH,
            category=Category.DISCOVERY,
            check_name="agent_manifest"
        )
    ]
    
    check_results = [
        CheckResult(
            name="agent_manifest",
            category=Category.DISCOVERY,
            status=CheckStatus.FAIL,
            score=0.0,
            weight=0.25,
            message="Missing /.well-known/agent-manifest.json",
            findings=findings,
            evidence={"url": "http://localhost:8765/perfect/.well-known/agent-manifest.json"}
        )
    ]
    
    categories = {
        Category.DISCOVERY: CategoryScore(
            category=Category.DISCOVERY,
            score=80.0,
            weight=0.25,
            grade=Grade.B,
            checks=check_results,
            top_findings=findings
        ),
        Category.IDENTITY: CategoryScore(
            category=Category.IDENTITY,
            score=40.0,
            weight=0.15,
            grade=Grade.D,
            checks=[],
            top_findings=[]
        ),
        Category.CAPABILITIES: CategoryScore(
            category=Category.CAPABILITIES,
            score=90.0,
            weight=0.25,
            grade=Grade.A,
            checks=[],
            top_findings=[]
        ),
        Category.COMMERCE: CategoryScore(
            category=Category.COMMERCE,
            score=60.0,
            weight=0.20,
            grade=Grade.C,
            checks=[],
            top_findings=[]
        ),
        Category.TRUST: CategoryScore(
            category=Category.TRUST,
            score=70.0,
            weight=0.15,
            grade=Grade.C,
            checks=[],
            top_findings=[]
        )
    }
    
    scorecard = Scorecard(
        url="http://localhost:8765/perfect",
        overall_score=73.0,
        grade=Grade.C,
        confidence_interval=ConfidenceInterval(lower=68.0, upper=78.0),
        percentile=42.0,
        categories=categories,
        total_checks=1,
        passed_checks=0,
        findings=findings,
        scan_duration_ms=1250.0,
        timestamp=timestamp,
        config_snapshot={}
    )
    
    return ScanResult(
        url="http://localhost:8765/perfect",
        scorecard=scorecard,
        check_results=check_results,
        raw_data={"rendered_html": "<html><body>Mock HTML</body></html>"},
        scan_version="0.1.0",
        timestamp=timestamp
    )


@pytest.mark.parametrize("format", ["html", "pdf", "json"])
def test_reporter_output(format: str, perfect_site_scan: ScanResult, tmp_path: Path) -> None:
    """Test output generation for HTML, PDF, and JSON reporters."""
    output = tmp_path / f"report.{format}"
    reporter = get_reporter(format)
    reporter.generate(perfect_site_scan, output)

    assert output.exists()
    assert output.stat().st_size > 1000  # Non-trivial output

    if format == "html":
        content = output.read_text(encoding="utf-8")
        assert "chart.js" in content.lower() or "chart" in content.lower()
        assert "radar" in content.lower()
        assert "73" in content  # Overall score
    elif format == "pdf":
        # Verify PDF magic bytes
        assert output.read_bytes()[:4] == b"%PDF"
    elif format == "json":
        data = json.loads(output.read_text(encoding="utf-8"))
        assert data["overall_score"] == 73
        assert "categories" in data


def test_terminal_reporter(perfect_site_scan: ScanResult) -> None:
    """Test that TerminalReporter renders output successfully to terminal."""
    reporter = get_reporter("terminal")
    
    # Test rendering scorecard
    reporter.render_scorecard(perfect_site_scan.scorecard)
    
    # Test rendering scan result in normal mode
    reporter.render_scan_result(perfect_site_scan, verbose=False)
    
    # Test rendering scan result in verbose mode
    reporter.render_scan_result(perfect_site_scan, verbose=True)
