"""Abstract base class for all AEO checks."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from aeo_audit.core.models import (
    Category,
    CheckContext,
    CheckResult,
    CheckStatus,
    Finding,
    Severity,
)


class BaseCheck(ABC):
    """Abstract base class for all AEO checks.

    Each check must define:
    - name: Unique identifier
    - category: Which AEO category (discovery, identity, etc.)
    - weight: Default weight within its category (0.0-1.0)
    - description: Human-readable description
    - timeout: Max execution time in seconds

    And implement:
    - run(): Execute the check and return a CheckResult
    """

    name: ClassVar[str]
    category: ClassVar[Category]
    weight: ClassVar[float]
    description: ClassVar[str] = ""
    timeout: ClassVar[float] = 10.0

    @abstractmethod
    async def run(self, context: CheckContext) -> CheckResult:
        """Execute this check against the given context.

        Args:
            context: The crawled page context with all extracted data.

        Returns:
            CheckResult with status, score, findings, and evidence.
        """
        ...

    def validate(self, result: CheckResult) -> bool:
        """Validate a check result for consistency.

        Args:
            result: The result to validate.

        Returns:
            True if the result is valid.
        """
        if result.score < 0.0 or result.score > 1.0:
            return False
        if result.status == CheckStatus.PASS and result.score < 0.5:
            return False
        return not (result.status == CheckStatus.FAIL and result.score > 0.5)

    def score(self, result: CheckResult) -> float:
        """Extract the normalized score (0.0-1.0) from a check result."""
        return result.score

    def _make_result(
        self,
        *,
        status: CheckStatus,
        score: float,
        message: str = "",
        findings: list[Finding] | None = None,
        evidence: dict[str, Any] | None = None,
        duration_ms: float = 0.0,
    ) -> CheckResult:
        """Helper to construct a CheckResult with this check's metadata."""
        return CheckResult(
            name=self.name,
            category=self.category,
            status=status,
            score=score,
            weight=self.weight,
            message=message,
            findings=findings or [],
            evidence=evidence or {},
            duration_ms=duration_ms,
        )

    def _make_finding(
        self,
        *,
        title: str,
        description: str,
        severity: Severity,
        recommendation: str = "",
        evidence: dict[str, Any] | None = None,
        effort: str = "medium",
        impact: str = "medium",
    ) -> Finding:
        """Helper to construct a Finding with this check's metadata."""
        return Finding(
            title=title,
            description=description,
            severity=severity,
            category=self.category,
            check_name=self.name,
            evidence=evidence or {},
            recommendation=recommendation,
            effort=effort,
            impact=impact,
        )
