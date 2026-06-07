"""Pydantic v2 domain models for AEO audit scanning and scoring."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Category(enum.StrEnum):
    """AEO check categories."""

    DISCOVERY = "discovery"
    IDENTITY = "identity"
    CAPABILITIES = "capabilities"
    COMMERCE = "commerce"
    TRUST = "trust"


class Severity(enum.StrEnum):
    """Finding severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class CheckStatus(enum.StrEnum):
    """Status of an individual check."""

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    SKIP = "skip"
    ERROR = "error"


class Grade(enum.StrEnum):
    """Overall grade."""

    A = "A"
    B = "B"
    C = "C"
    D = "D"
    F = "F"


class Finding(BaseModel):
    """A single finding from a check."""

    model_config = {"strict": True}

    title: str = Field(..., description="Short description of the finding")
    description: str = Field(..., description="Detailed explanation")
    severity: Severity = Field(..., description="Impact severity")
    category: Category = Field(..., description="Which AEO category")
    check_name: str = Field(..., description="Name of the check that produced this")
    evidence: dict[str, Any] = Field(
        default_factory=dict, description="Raw evidence data"
    )
    recommendation: str = Field(default="", description="Suggested fix")
    effort: str = Field(
        default="medium", description="Implementation effort: low/medium/high"
    )
    impact: str = Field(
        default="medium", description="Business impact: low/medium/high"
    )


class CheckResult(BaseModel):
    """Result of running a single check."""

    model_config = {"strict": True}

    name: str = Field(..., description="Check identifier")
    category: Category
    status: CheckStatus
    score: float = Field(..., ge=0.0, le=1.0, description="Normalized score 0.0-1.0")
    weight: float = Field(
        ..., ge=0.0, le=1.0, description="Check weight within category"
    )
    message: str = Field(default="", description="Human-readable result message")
    findings: list[Finding] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(
        default_factory=dict, description="Raw data collected"
    )
    duration_ms: float = Field(
        default=0.0, description="Check execution time in milliseconds"
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class CategoryScore(BaseModel):
    """Score for a single category."""

    model_config = {"strict": True}

    category: Category
    score: float = Field(..., ge=0.0, le=100.0)
    weight: float = Field(..., ge=0.0, le=1.0)
    grade: Grade
    checks: list[CheckResult] = Field(default_factory=list)
    top_findings: list[Finding] = Field(
        default_factory=list, description="Top 3 findings"
    )


class ConfidenceInterval(BaseModel):
    """Bootstrap confidence interval."""

    model_config = {"strict": True}

    lower: float = Field(..., ge=0.0, le=100.0)
    upper: float = Field(..., ge=0.0, le=100.0)
    confidence_level: float = Field(default=0.95)
    samples: int = Field(default=1000)


class Scorecard(BaseModel):
    """Complete scan scorecard."""

    model_config = {"strict": True}

    url: str
    overall_score: float = Field(..., ge=0.0, le=100.0)
    grade: Grade
    confidence_interval: ConfidenceInterval
    percentile: float | None = Field(default=None, ge=0.0, le=100.0)
    categories: dict[Category, CategoryScore] = Field(default_factory=dict)
    total_checks: int = Field(default=0)
    passed_checks: int = Field(default=0)
    findings: list[Finding] = Field(default_factory=list)
    scan_duration_ms: float = Field(default=0.0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    config_snapshot: dict[str, Any] = Field(default_factory=dict)


class ScanResult(BaseModel):
    """Full scan result including metadata."""

    model_config = {"strict": True}

    url: str
    scorecard: Scorecard
    check_results: list[CheckResult] = Field(default_factory=list)
    raw_data: dict[str, Any] = Field(
        default_factory=dict, description="Collected page data"
    )
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    scan_version: str = Field(default="0.1.0")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class CheckContext(BaseModel):
    """Context passed to each check during execution."""

    model_config = {"strict": True}

    url: str
    base_url: str = Field(..., description="Base URL (scheme + host)")
    headers: dict[str, str] = Field(default_factory=dict)
    rendered_html: str = Field(default="")
    raw_html: str = Field(default="")
    extracted_metadata: dict[str, Any] = Field(
        default_factory=dict, description="JSON-LD, microdata, OG"
    )
    dns_records: dict[str, list[str]] = Field(default_factory=dict)
    response_headers: dict[str, str] = Field(default_factory=dict)
    robots_txt: str | None = Field(default=None)
    sitemap_xml: str | None = Field(default=None)
    timeout: float = Field(default=10.0)


class Config(BaseModel):
    """Application configuration loaded from config.yaml."""

    model_config = {"strict": True}

    weights: dict[str, float] = Field(default_factory=dict)
    checks: dict[str, dict[str, float]] = Field(default_factory=dict)
    thresholds: dict[str, int] = Field(default_factory=dict)
    crawler: dict[str, Any] = Field(default_factory=dict)
    http: dict[str, Any] = Field(default_factory=dict)
    cache: dict[str, Any] = Field(default_factory=dict)
    benchmarks: dict[str, Any] = Field(default_factory=dict)
    reporting: dict[str, Any] = Field(default_factory=dict)
