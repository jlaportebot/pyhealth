"""Scoring algorithm for pyhealth."""

from __future__ import annotations

from pyhealth.models import CheckCategory, ProjectHealthReport

# Category weights for overall score calculation
CATEGORY_WEIGHTS = {
    CheckCategory.SECURITY: 0.25,
    CheckCategory.DEPENDENCIES: 0.20,
    CheckCategory.CODE_QUALITY: 0.15,
    CheckCategory.TESTS: 0.15,
    CheckCategory.DOCUMENTATION: 0.10,
    CheckCategory.CI_CD: 0.10,
    CheckCategory.STRUCTURE: 0.05,
}

# Grade thresholds
GRADE_THRESHOLDS = {
    "A": 90,
    "B": 80,
    "C": 70,
    "D": 60,
    # F is anything below 60
}


def calculate_overall_score(report: ProjectHealthReport) -> float:
    """Calculate weighted overall score from check results."""
    total_weight = 0.0
    weighted_sum = 0.0

    for result in report.check_results:
        weight = CATEGORY_WEIGHTS.get(result.category, 0.0)
        if weight > 0:
            weighted_sum += result.score * weight
            total_weight += weight

    if total_weight == 0:
        return 0.0

    return round(weighted_sum / total_weight, 1)


def calculate_grade(score: float) -> str:
    """Calculate letter grade from score."""
    for grade, threshold in GRADE_THRESHOLDS.items():
        if score >= threshold:
            return grade
    return "F"


def calculate_category_scores(report: ProjectHealthReport) -> dict[str, float]:
    """Calculate average score per category."""
    category_scores: dict[str, list[float]] = {}

    for result in report.check_results:
        cat_name = result.category.value
        if cat_name not in category_scores:
            category_scores[cat_name] = []
        category_scores[cat_name].append(result.score)

    return {cat: round(sum(scores) / len(scores), 1) for cat, scores in category_scores.items()}


def get_priority_issues(report: ProjectHealthReport, limit: int = 10) -> list[tuple[float, str]]:
    """Get top priority issues sorted by severity and category weight."""
    severity_weights = {
        "critical": 1000,
        "error": 100,
        "warning": 10,
        "info": 1,
    }

    all_issues = []
    for result in report.check_results:
        cat_weight = CATEGORY_WEIGHTS.get(result.category, 0.0)
        for issue in result.issues:
            priority = severity_weights.get(issue.severity.value, 1) * (1 + cat_weight)
            all_issues.append((priority, issue))

    # Sort by priority descending
    all_issues.sort(key=lambda x: x[0], reverse=True)

    return [
        (priority, f"[{issue.severity.value.upper()}] {issue.message}")
        for priority, issue in all_issues[:limit]
    ]
