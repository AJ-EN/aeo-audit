"""Tests for the scoring module."""

from __future__ import annotations

import pytest

from aeo_audit.core.models import Category, CheckResult, CheckStatus, Config, Grade, Severity, Finding
from aeo_audit.core.scoring import (
    bootstrap_confidence_interval,
    calculate_category_score,
    calculate_grade,
    calculate_score,
    normalize_to_percentile,
)


class TestCalculateGrade:
    """Tests for grade calculation."""

    def test_grade_a(self) -> None:
        thresholds = {"grade_A": 90, "grade_B": 75, "grade_C": 60, "grade_D": 40}
        assert calculate_grade(95.0, thresholds) == Grade.A
        assert calculate_grade(90.0, thresholds) == Grade.A

    def test_grade_b(self) -> None:
        thresholds = {"grade_A": 90, "grade_B": 75, "grade_C": 60, "grade_D": 40}
        assert calculate_grade(89.9, thresholds) == Grade.B
        assert calculate_grade(75.0, thresholds) == Grade.B

    def test_grade_c(self) -> None:
        thresholds = {"grade_A": 90, "grade_B": 75, "grade_C": 60, "grade_D": 40}
        assert calculate_grade(74.9, thresholds) == Grade.C
        assert calculate_grade(60.0, thresholds) == Grade.C

    def test_grade_d(self) -> None:
        thresholds = {"grade_A": 90, "grade_B": 75, "grade_C": 60, "grade_D": 40}
        assert calculate_grade(59.9, thresholds) == Grade.D
        assert calculate_grade(40.0, thresholds) == Grade.D

    def test_grade_f(self) -> None:
        thresholds = {"grade_A": 90, "grade_B": 75, "grade_C": 60, "grade_D": 40}
        assert calculate_grade(39.9, thresholds) == Grade.F
        assert calculate_grade(0.0, thresholds) == Grade.F


class TestPercentileNormalization:
    """Tests for percentile calculations."""

    def test_empty_benchmarks(self) -> None:
        assert normalize_to_percentile(85.0, None) is None
        assert normalize_to_percentile(85.0, []) is None

    def test_percentile_calculation(self) -> None:
        benchmarks = [10.0, 20.0, 30.0, 40.0]
        # 25 is greater than 10, 20. So 2/4 = 50%
        assert normalize_to_percentile(25.0, benchmarks) == 50.0
        # 10 is greater than or equal to 10. So 1/4 = 25%
        assert normalize_to_percentile(10.0, benchmarks) == 25.0
        # 5 is greater than none. So 0%
        assert normalize_to_percentile(5.0, benchmarks) == 0.0
        # 50 is greater than all. So 100%
        assert normalize_to_percentile(50.0, benchmarks) == 100.0


class TestCategoryScoring:
    """Tests for category scoring logic."""

    def test_category_score_with_skipped_checks(self) -> None:
        checks = [
            CheckResult(name="check1", category=Category.DISCOVERY, status=CheckStatus.PASS, score=1.0, weight=0.6),
            CheckResult(name="check2", category=Category.DISCOVERY, status=CheckStatus.SKIP, score=0.0, weight=0.4),
        ]
        weights = {"check1": 0.6, "check2": 0.4}
        thresholds = {"grade_A": 90, "grade_B": 75}
        
        # With skipped check2, check1 should be re-weighted to 100% of the category
        score = calculate_category_score(checks, Category.DISCOVERY, weights, thresholds)
        assert score.score == 100.0
        assert score.grade == Grade.A

    def test_category_score_basic(self) -> None:
        checks = [
            CheckResult(name="check1", category=Category.DISCOVERY, status=CheckStatus.PASS, score=1.0, weight=0.5),
            CheckResult(name="check2", category=Category.DISCOVERY, status=CheckStatus.FAIL, score=0.0, weight=0.5),
        ]
        weights = {"check1": 0.5, "check2": 0.5}
        thresholds = {"grade_A": 90, "grade_B": 75, "grade_C": 60, "grade_D": 40}
        
        score = calculate_category_score(checks, Category.DISCOVERY, weights, thresholds)
        assert score.score == 50.0
        assert score.grade == Grade.D


class TestScoringBootstrap:
    """Tests for bootstrap confidence interval calculation."""

    def test_bootstrap_empty(self) -> None:
        ci = bootstrap_confidence_interval([], {}, {})
        assert ci.lower == 0.0
        assert ci.upper == 0.0

    def test_bootstrap_reproducibility(self) -> None:
        checks = [
            CheckResult(name="check1", category=Category.DISCOVERY, status=CheckStatus.PASS, score=1.0, weight=1.0)
        ]
        category_weights = {"discovery": 1.0}
        check_weights = {"discovery": {"check1": 1.0}}
        
        ci = bootstrap_confidence_interval(checks, category_weights, check_weights, n_samples=100)
        assert ci.lower == 100.0
        assert ci.upper == 100.0
