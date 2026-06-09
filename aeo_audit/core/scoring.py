"""Weighted scoring, normalization, confidence intervals, and grading."""

from __future__ import annotations

import json
import random
from typing import TYPE_CHECKING

from aeo_audit.core.models import (
    Category,
    CategoryScore,
    CheckResult,
    CheckStatus,
    ConfidenceInterval,
    Config,
    Grade,
    Scorecard,
)

if TYPE_CHECKING:
    from aeo_audit.core.models import Finding


def calculate_grade(score: float, thresholds: dict[str, int]) -> Grade:
    """Map a 0-100 score to a letter grade (absolute thresholds).

    Used for per-category grades. Grade: A>=90, B>=75, C>=60, D>=40, F<40.
    """
    if score >= thresholds.get("grade_A", 90):
        return Grade.A
    elif score >= thresholds.get("grade_B", 75):
        return Grade.B
    elif score >= thresholds.get("grade_C", 60):
        return Grade.C
    elif score >= thresholds.get("grade_D", 40):
        return Grade.D
    else:
        return Grade.F


# Default percentile cutoffs for relative grading (rank against the benchmark
# corpus). A = top 10% of agent-readiness today, and the bar rises as the
# benchmark corpus improves.
DEFAULT_GRADE_PERCENTILES: dict[str, float] = {"A": 90.0, "B": 70.0, "C": 40.0, "D": 15.0}


def grade_from_percentile(percentile: float, cutoffs: dict[str, float] | None = None) -> Grade:
    """Map a 0-100 percentile rank to a letter grade.

    Relative grading: a site's grade reflects how it ranks against the
    benchmark corpus, not an absolute score. This keeps grades meaningful while
    agent-readiness standards are still nascent (every absolute score is low).
    """
    c = cutoffs or DEFAULT_GRADE_PERCENTILES
    if percentile >= c.get("A", 90.0):
        return Grade.A
    elif percentile >= c.get("B", 70.0):
        return Grade.B
    elif percentile >= c.get("C", 40.0):
        return Grade.C
    elif percentile >= c.get("D", 15.0):
        return Grade.D
    else:
        return Grade.F


def _resolve_benchmark_path(pct_file: str) -> str | None:
    """Resolve a benchmark data path robustly across run contexts.

    Tries the path as given (cwd-relative), then relative to the repository
    root (package parent), so scoring works whether invoked from the repo, an
    installed package, or the bundled binary.
    """
    from pathlib import Path

    candidates = [
        Path(pct_file),
        Path(__file__).resolve().parent.parent.parent / pct_file,
        Path(__file__).resolve().parent.parent / pct_file,
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return None


def _calculate_overall_score_raw(
    check_results: list[CheckResult],
    category_weights: dict[str, float],
    check_weights: dict[str, dict[str, float]],
) -> float:
    """Helper to calculate raw overall score from checks."""
    by_category: dict[Category, list[CheckResult]] = {cat: [] for cat in Category}
    for r in check_results:
        by_category[r.category].append(r)

    cat_scores = {}
    for cat in Category:
        results = by_category[cat]
        weights = check_weights.get(cat.value, {})
        total_weight = 0.0
        weighted_score_sum = 0.0
        for r in results:
            if r.status == CheckStatus.SKIP:
                continue
            weight = weights.get(r.name, 0.0)
            total_weight += weight
            weighted_score_sum += r.score * weight
        cat_scores[cat] = (weighted_score_sum / total_weight) * 100.0 if total_weight > 0.0 else 0.0

    overall_score = 0.0
    category_weight_sum = 0.0
    for cat in Category:
        weight = category_weights.get(cat.value, 0.0)
        overall_score += cat_scores[cat] * weight
        category_weight_sum += weight

    return overall_score / category_weight_sum if category_weight_sum > 0.0 else 0.0


def bootstrap_confidence_interval(
    check_results: list[CheckResult],
    category_weights: dict[str, float],
    check_weights: dict[str, dict[str, float]],
    n_samples: int = 1000,
    confidence_level: float = 0.95,
) -> ConfidenceInterval:
    """Compute bootstrap confidence interval for the overall score.

    Resamples check results with replacement, recalculates score each time,
    then returns the percentile-based CI.
    """
    if not check_results:
        return ConfidenceInterval(
            lower=0.0,
            upper=0.0,
            confidence_level=confidence_level,
            samples=n_samples,
        )

    # Deterministic seed for reproducible tests
    state = random.getstate()
    random.seed(42)

    scores = []
    for _ in range(n_samples):
        sample = [random.choice(check_results) for _ in range(len(check_results))]
        score = _calculate_overall_score_raw(sample, category_weights, check_weights)
        scores.append(score)

    random.setstate(state)
    scores.sort()

    lower_idx = int(n_samples * ((1.0 - confidence_level) / 2.0))
    upper_idx = int(n_samples * (1.0 - (1.0 - confidence_level) / 2.0))

    lower_idx = max(0, min(lower_idx, n_samples - 1))
    upper_idx = max(0, min(upper_idx, n_samples - 1))

    return ConfidenceInterval(
        lower=scores[lower_idx],
        upper=scores[upper_idx],
        confidence_level=confidence_level,
        samples=n_samples,
    )


def normalize_to_percentile(
    score: float,
    benchmark_data: list[float] | None = None,
) -> float | None:
    """Normalize score against benchmark percentile data.

    Args:
        score: Raw 0-100 score.
        benchmark_data: Sorted list of benchmark scores.

    Returns:
        Percentile rank (0-100) or None if no benchmark data.
    """
    if not benchmark_data:
        return None
    count = sum(1 for s in benchmark_data if s <= score)
    return (count / len(benchmark_data)) * 100.0


def calculate_category_score(
    check_results: list[CheckResult],
    category: Category,
    check_weights: dict[str, float],
    thresholds: dict[str, int],
) -> CategoryScore:
    """Calculate weighted score for a single category.

    Category score = weighted average of check raw_scores.
    """
    total_weight = 0.0
    weighted_score_sum = 0.0
    checks_in_category = []
    findings: list[Finding] = []

    for r in check_results:
        if r.category == category:
            checks_in_category.append(r)
            findings.extend(r.findings)
            if r.status == CheckStatus.SKIP:
                continue
            weight = check_weights.get(r.name, 0.0)
            total_weight += weight
            weighted_score_sum += r.score * weight

    score = (weighted_score_sum / total_weight) * 100.0 if total_weight > 0.0 else 0.0
    grade = calculate_grade(score, thresholds)

    # Sort findings by severity
    severity_map = {"critical": 5, "high": 4, "medium": 3, "low": 2, "info": 1}
    sorted_findings = sorted(
        findings,
        key=lambda f: severity_map.get(f.severity.value, 1),
        reverse=True,
    )

    return CategoryScore(
        category=category,
        score=score,
        weight=0.0,  # Loaded in calculate_score
        grade=grade,
        checks=checks_in_category,
        top_findings=sorted_findings[:3],
    )


def calculate_score(check_results: list[CheckResult], config: Config) -> Scorecard:
    """Calculate the full AEO scorecard.

    Algorithm:
    1. Each check: raw_score = passed_checks / total_checks (0.0-1.0)
    2. Category score = weighted average of check raw_scores (weights from config)
    3. Overall = weighted average of 5 category scores
    4. Normalize to 0-100 with percentile adjustment
    5. Confidence interval: bootstrap 1000 samples -> 95% CI
    6. Grade: A>=90, B>=75, C>=60, D>=40, F<40
    """
    # 1. Category scores
    categories = {}
    for cat in Category:
        check_weights = config.checks.get(cat.value, {})
        cat_score = calculate_category_score(
            check_results,
            cat,
            check_weights,
            config.thresholds,
        )
        cat_score.weight = config.weights.get(cat.value, 0.0)
        categories[cat] = cat_score

    # 2. Overall score
    overall_score = _calculate_overall_score_raw(
        check_results,
        config.weights,
        config.checks,
    )
    # Absolute grade is the fallback when no benchmark corpus is available.
    grade = calculate_grade(overall_score, config.thresholds)

    # 3. Bootstrap CI
    n_samples = config.benchmarks.get("bootstrap_samples", 1000)
    conf_level = config.benchmarks.get("confidence_level", 0.95)
    ci = bootstrap_confidence_interval(
        check_results,
        config.weights,
        config.checks,
        n_samples=n_samples,
        confidence_level=conf_level,
    )

    # 4. Percentile normalization + relative grading
    benchmark_data = None
    pct_file = config.benchmarks.get("percentile_data")
    if pct_file:
        resolved = _resolve_benchmark_path(pct_file)
        if resolved:
            try:
                with open(resolved, encoding="utf-8") as f:
                    bench_json = json.load(f)
                    benchmark_data = bench_json.get("percentiles")
            except Exception:
                pass
    percentile = normalize_to_percentile(overall_score, benchmark_data)

    # When a benchmark corpus is available, grade relative to it (rank-based);
    # otherwise fall back to the absolute grade computed above.
    if percentile is not None:
        grade = grade_from_percentile(
            percentile, config.benchmarks.get("grade_percentiles")
        )

    # Calculate counts
    total_checks = len(check_results)
    passed_checks = sum(1 for r in check_results if r.status == CheckStatus.PASS)

    all_findings = []
    for r in check_results:
        all_findings.extend(r.findings)

    return Scorecard(
        url="",
        overall_score=overall_score,
        grade=grade,
        confidence_interval=ci,
        percentile=percentile,
        benchmark_size=len(benchmark_data) if benchmark_data else 0,
        categories=categories,
        total_checks=total_checks,
        passed_checks=passed_checks,
        findings=all_findings,
        config_snapshot=config.model_dump(),
    )
