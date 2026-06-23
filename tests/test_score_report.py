"""Tests for pyhealth scoring and report generation."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from pyhealth.models import CheckCategory, CheckResult, Issue, ProjectHealthReport, Severity
from pyhealth.report import ReportGenerator
from pyhealth.score import (
    calculate_category_scores,
    calculate_grade,
    calculate_overall_score,
    get_priority_issues,
)


class TestScore:
    def test_calculate_overall_score(self) -> None:
        results = [
            CheckResult(name="Security", category=CheckCategory.SECURITY, passed=True, score=90.0),
            CheckResult(
                name="Dependencies", category=CheckCategory.DEPENDENCIES, passed=True, score=80.0
            ),
            CheckResult(
                name="Code Quality", category=CheckCategory.CODE_QUALITY, passed=False, score=60.0
            ),
            CheckResult(name="Tests", category=CheckCategory.TESTS, passed=True, score=100.0),
            CheckResult(
                name="Documentation", category=CheckCategory.DOCUMENTATION, passed=True, score=90.0
            ),
            CheckResult(name="CI/CD", category=CheckCategory.CI_CD, passed=True, score=85.0),
            CheckResult(
                name="Structure", category=CheckCategory.STRUCTURE, passed=True, score=95.0
            ),
        ]
        report = ProjectHealthReport(
            project_path=Path("/tmp"),
            timestamp=datetime.now(),
            overall_score=0.0,
            grade="F",
            check_results=results,
        )
        score = calculate_overall_score(report)
        # Weighted: 0.25*90 + 0.20*80 + 0.15*60 + 0.15*100 + 0.10*90 + 0.10*85 + 0.05*95 = 22.5 + 16 + 9 + 15 + 9 + 8.5 + 4.75 = 84.75
        assert score == 84.8  # rounded to 1 decimal

    def test_calculate_grade(self) -> None:
        assert calculate_grade(95.0) == "A"
        assert calculate_grade(85.0) == "B"
        assert calculate_grade(75.0) == "C"
        assert calculate_grade(65.0) == "D"
        assert calculate_grade(55.0) == "F"
        assert calculate_grade(90.0) == "A"  # boundary
        assert calculate_grade(80.0) == "B"  # boundary
        assert calculate_grade(70.0) == "C"  # boundary
        assert calculate_grade(60.0) == "D"  # boundary

    def test_calculate_category_scores(self) -> None:
        results = [
            CheckResult(name="Sec 1", category=CheckCategory.SECURITY, passed=True, score=90.0),
            CheckResult(name="Sec 2", category=CheckCategory.SECURITY, passed=True, score=80.0),
            CheckResult(
                name="Code 1", category=CheckCategory.CODE_QUALITY, passed=False, score=60.0
            ),
        ]
        report = ProjectHealthReport(
            project_path=Path("/tmp"),
            timestamp=datetime.now(),
            overall_score=0.0,
            grade="F",
            check_results=results,
        )
        scores = calculate_category_scores(report)
        assert scores["security"] == 85.0  # (90+80)/2
        assert scores["code_quality"] == 60.0

    def test_get_priority_issues(self) -> None:
        issues = [
            Issue(
                category=CheckCategory.SECURITY,
                severity=Severity.CRITICAL,
                message="Critical security",
            ),
            Issue(
                category=CheckCategory.DEPENDENCIES, severity=Severity.ERROR, message="Dep error"
            ),
            Issue(
                category=CheckCategory.CODE_QUALITY,
                severity=Severity.WARNING,
                message="Code warning",
            ),
            Issue(category=CheckCategory.DOCUMENTATION, severity=Severity.INFO, message="Doc info"),
        ]
        results = [
            CheckResult(
                name="Security",
                category=CheckCategory.SECURITY,
                passed=False,
                score=50.0,
                issues=[issues[0]],
            ),
            CheckResult(
                name="Deps",
                category=CheckCategory.DEPENDENCIES,
                passed=False,
                score=70.0,
                issues=[issues[1]],
            ),
            CheckResult(
                name="Code",
                category=CheckCategory.CODE_QUALITY,
                passed=True,
                score=80.0,
                issues=[issues[2]],
            ),
            CheckResult(
                name="Docs",
                category=CheckCategory.DOCUMENTATION,
                passed=True,
                score=90.0,
                issues=[issues[3]],
            ),
        ]
        report = ProjectHealthReport(
            project_path=Path("/tmp"),
            timestamp=datetime.now(),
            overall_score=0.0,
            grade="F",
            check_results=results,
        )
        priority = get_priority_issues(report, limit=3)
        assert len(priority) == 3
        # Critical security should be first (highest severity + highest category weight)
        assert "Critical security" in priority[0][1]
        # Dep error should be second
        assert "Dep error" in priority[1][1]
        # Code warning should be third
        assert "Code warning" in priority[2][1]


class TestReportGenerator:
    def test_json_report(self, tmp_path: Path) -> None:
        result = CheckResult(
            name="Test Check", category=CheckCategory.SECURITY, passed=True, score=100.0
        )
        report = ProjectHealthReport(
            project_path=Path("/tmp/test"),
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            overall_score=100.0,
            grade="A",
            check_results=[result],
        )
        generator = ReportGenerator(report)
        json_str = generator.to_json()
        assert '"overall_score": 100.0' in json_str
        assert '"grade": "A"' in json_str
        assert '"name": "Test Check"' in json_str

    def test_json_report_to_file(self, tmp_path: Path) -> None:
        result = CheckResult(
            name="Test Check", category=CheckCategory.SECURITY, passed=True, score=100.0
        )
        report = ProjectHealthReport(
            project_path=Path("/tmp/test"),
            timestamp=datetime.now(),
            overall_score=100.0,
            grade="A",
            check_results=[result],
        )
        generator = ReportGenerator(report)
        output_file = tmp_path / "report.json"
        generator.to_json(output_file)
        assert output_file.exists()
        content = output_file.read_text()
        assert '"overall_score": 100.0' in content

    def test_html_report(self, tmp_path: Path) -> None:
        result = CheckResult(
            name="Test Check", category=CheckCategory.SECURITY, passed=True, score=100.0
        )
        report = ProjectHealthReport(
            project_path=Path("/tmp/test"),
            timestamp=datetime.now(),
            overall_score=100.0,
            grade="A",
            check_results=[result],
        )
        generator = ReportGenerator(report)
        html = generator.to_html()
        assert "<html" in html
        assert "pyhealth Report" in html
        assert "100.0%" in html
        assert "Grade A" in html
        assert "Test Check" in html

    def test_html_report_to_file(self, tmp_path: Path) -> None:
        result = CheckResult(
            name="Test Check", category=CheckCategory.SECURITY, passed=True, score=100.0
        )
        report = ProjectHealthReport(
            project_path=Path("/tmp/test"),
            timestamp=datetime.now(),
            overall_score=100.0,
            grade="A",
            check_results=[result],
        )
        generator = ReportGenerator(report)
        output_file = tmp_path / "report.html"
        generator.to_html(output_file)
        assert output_file.exists()
        content = output_file.read_text()
        assert "pyhealth Report" in content

    def test_markdown_report(self, tmp_path: Path) -> None:
        result = CheckResult(
            name="Test Check", category=CheckCategory.SECURITY, passed=True, score=100.0
        )
        report = ProjectHealthReport(
            project_path=Path("/tmp/test"),
            timestamp=datetime.now(),
            overall_score=100.0,
            grade="A",
            check_results=[result],
        )
        generator = ReportGenerator(report)
        md = generator.to_markdown()
        assert "# pyhealth Report" in md
        assert "100.0%" in md
        assert "Grade A" in md
        assert "Test Check" in md

    def test_markdown_report_to_file(self, tmp_path: Path) -> None:
        result = CheckResult(
            name="Test Check", category=CheckCategory.SECURITY, passed=True, score=100.0
        )
        report = ProjectHealthReport(
            project_path=Path("/tmp/test"),
            timestamp=datetime.now(),
            overall_score=100.0,
            grade="A",
            check_results=[result],
        )
        generator = ReportGenerator(report)
        output_file = tmp_path / "report.md"
        generator.to_markdown(output_file)
        assert output_file.exists()
        content = output_file.read_text()
        assert "# pyhealth Report" in content

    def test_get_grade_color(self) -> None:
        result = CheckResult(
            name="Test", category=CheckCategory.STRUCTURE, passed=True, score=100.0
        )
        report = ProjectHealthReport(
            project_path=Path("/tmp"),
            timestamp=datetime.now(),
            overall_score=100.0,
            grade="A",
            check_results=[result],
        )
        generator = ReportGenerator(report)
        assert generator._get_grade_color("A") == "#38a169"
        assert generator._get_grade_color("B") == "#48bb78"
        assert generator._get_grade_color("C") == "#d69e2e"
        assert generator._get_grade_color("D") == "#ed8936"
        assert generator._get_grade_color("F") == "#e53e3e"
        assert generator._get_grade_color("X") == "#718096"
