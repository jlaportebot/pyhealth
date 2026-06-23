"""pyhealth — Python Project Health Analyzer."""

from __future__ import annotations

__version__ = "0.1.0"
__author__ = "jlaportebot"
__license__ = "MIT"

from pyhealth.cli import main
from pyhealth.models import CheckCategory, CheckResult, Issue, ProjectHealthReport, Severity
from pyhealth.report import ReportGenerator
from pyhealth.score import calculate_grade, calculate_overall_score

__all__ = [
    "CheckCategory",
    "CheckResult",
    "Issue",
    "ProjectHealthReport",
    "ReportGenerator",
    "Severity",
    "calculate_grade",
    "calculate_overall_score",
    "main",
]
