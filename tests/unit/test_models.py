"""Tests for core Pydantic models."""

from __future__ import annotations

import pytest

from aeo_audit.core.models import (
    Category,
    CheckContext,
    CheckResult,
    CheckStatus,
    Config,
    Finding,
    Grade,
    Scorecard,
    Severity,
)


class TestFinding:
    """Tests for the Finding model."""

    def test_create_finding(self, sample_finding: Finding) -> None:
        assert sample_finding.title == "Missing agent manifest"
        assert sample_finding.severity == Severity.HIGH
        assert sample_finding.category == Category.DISCOVERY

    def test_finding_defaults(self) -> None:
        finding = Finding(
            title="Test",
            description="Test finding",
            severity=Severity.LOW,
            category=Category.TRUST,
            check_name="test_check",
        )
        assert finding.evidence == {}
        assert finding.recommendation == ""
        assert finding.effort == "medium"
        assert finding.impact == "medium"


class TestCheckResult:
    """Tests for the CheckResult model."""

    def test_valid_score_range(self) -> None:
        result = CheckResult(
            name="test",
            category=Category.DISCOVERY,
            status=CheckStatus.PASS,
            score=0.85,
            weight=0.25,
        )
        assert 0.0 <= result.score <= 1.0

    def test_invalid_score_rejected(self) -> None:
        with pytest.raises(Exception):
            CheckResult(
                name="test",
                category=Category.DISCOVERY,
                status=CheckStatus.PASS,
                score=1.5,  # Out of range
                weight=0.25,
            )


class TestCheckContext:
    """Tests for the CheckContext model."""

    def test_create_context(self, sample_check_context: CheckContext) -> None:
        assert sample_check_context.url == "https://example.com"
        assert sample_check_context.timeout == 10.0


class TestConfig:
    """Tests for the Config model."""

    def test_create_config(self, sample_config: Config) -> None:
        assert sample_config.weights["discovery"] == 0.25
        assert sample_config.thresholds["grade_A"] == 90
