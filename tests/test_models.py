"""Tests for pyhealth models."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from pyhealth.models import (
    CheckCategory,
    CheckResult,
    Issue,
    ProjectHealthReport,
    Severity,
)


class TestIssue:
    def test_issue_creation(self) -> None:
        issue = Issue(
            category=CheckCategory.DEPENDENCIES,
            severity=Severity.WARNING,
            message="Test issue",
            file_path="test.py",
            line_number=10,
            rule_id="test-rule",
            suggestion="Fix it",
        )
        assert issue.category == CheckCategory.DEPENDENCIES
        assert issue.severity == Severity.WARNING
        assert issue.message == "Test issue"
        assert issue.file_path == "test.py"
        assert issue.line_number == 10
        assert issue.rule_id == "test-rule"
        assert issue.suggestion == "Fix it"

    def test_issue_to_dict(self) -> None:
        issue = Issue(
            category=CheckCategory.SECURITY,
            severity=Severity.CRITICAL,
            message="Security issue",
        )
        d = issue.to_dict()
        assert d["category"] == "security"
        assert d["severity"] == "critical"
        assert d["message"] == "Security issue"
        assert d["file_path"] is None
        assert d["line_number"] is None


class TestCheckResult:
    def test_check_result_creation(self) -> None:
        issue = Issue(
            category=CheckCategory.CODE_QUALITY,
            severity=Severity.ERROR,
            message="Lint error",
        )
        result = CheckResult(
            name="Code Quality Check",
            category=CheckCategory.CODE_QUALITY,
            passed=False,
            score=75.0,
            issues=[issue],
            metrics={"files_checked": 10},
        )
        assert result.name == "Code Quality Check"
        assert result.category == CheckCategory.CODE_QUALITY
        assert result.passed is False
        assert result.score == 75.0
        assert len(result.issues) == 1
        assert result.metrics["files_checked"] == 10

    def test_check_result_to_dict(self) -> None:
        result = CheckResult(
            name="Test Check",
            category=CheckCategory.TESTS,
            passed=True,
            score=100.0,
        )
        d = result.to_dict()
        assert d["name"] == "Test Check"
        assert d["category"] == "tests"
        assert d["passed"] is True
        assert d["score"] == 100.0
        assert d["issues"] == []


class TestProjectHealthReport:
    def test_report_creation(self) -> None:
        result = CheckResult(
            name="Test Check",
            category=CheckCategory.DEPENDENCIES,
            passed=True,
            score=90.0,
        )
        report = ProjectHealthReport(
            project_path=Path("/tmp/test"),
            timestamp=datetime.now(),
            overall_score=85.0,
            grade="B",
            check_results=[result],
        )
        assert report.project_path == Path("/tmp/test")
        assert report.overall_score == 85.0
        assert report.grade == "B"
        assert len(report.check_results) == 1

    def test_get_issues_by_severity(self) -> None:
        issues = [
            Issue(
                category=CheckCategory.DEPENDENCIES, severity=Severity.CRITICAL, message="Critical"
            ),
            Issue(category=CheckCategory.DEPENDENCIES, severity=Severity.ERROR, message="Error"),
            Issue(
                category=CheckCategory.CODE_QUALITY, severity=Severity.WARNING, message="Warning"
            ),
            Issue(category=CheckCategory.CODE_QUALITY, severity=Severity.INFO, message="Info"),
        ]
        results = [
            CheckResult(
                name="Check 1",
                category=CheckCategory.DEPENDENCIES,
                passed=False,
                score=50.0,
                issues=issues[:2],
            ),
            CheckResult(
                name="Check 2",
                category=CheckCategory.CODE_QUALITY,
                passed=True,
                score=90.0,
                issues=issues[2:],
            ),
        ]
        report = ProjectHealthReport(
            project_path=Path("/tmp/test"),
            timestamp=datetime.now(),
            overall_score=70.0,
            grade="C",
            check_results=results,
        )
        critical = report.get_issues_by_severity(Severity.CRITICAL)
        error = report.get_issues_by_severity(Severity.ERROR)
        warning = report.get_issues_by_severity(Severity.WARNING)
        info = report.get_issues_by_severity(Severity.INFO)
        assert len(critical) == 1
        assert len(error) == 1
        assert len(warning) == 1
        assert len(info) == 1

    def test_get_issues_by_category(self) -> None:
        issues = [
            Issue(
                category=CheckCategory.DEPENDENCIES, severity=Severity.WARNING, message="Dep issue"
            ),
            Issue(
                category=CheckCategory.CODE_QUALITY, severity=Severity.WARNING, message="Code issue"
            ),
        ]
        results = [
            CheckResult(
                name="Dep Check",
                category=CheckCategory.DEPENDENCIES,
                passed=True,
                score=90.0,
                issues=[issues[0]],
            ),
            CheckResult(
                name="Code Check",
                category=CheckCategory.CODE_QUALITY,
                passed=True,
                score=90.0,
                issues=[issues[1]],
            ),
        ]
        report = ProjectHealthReport(
            project_path=Path("/tmp/test"),
            timestamp=datetime.now(),
            overall_score=90.0,
            grade="A",
            check_results=results,
        )
        dep_issues = report.get_issues_by_category(CheckCategory.DEPENDENCIES)
        code_issues = report.get_issues_by_category(CheckCategory.CODE_QUALITY)
        assert len(dep_issues) == 1
        assert len(code_issues) == 1
        assert dep_issues[0].message == "Dep issue"
        assert code_issues[0].message == "Code issue"

    def test_report_to_dict(self) -> None:
        result = CheckResult(
            name="Test Check",
            category=CheckCategory.SECURITY,
            passed=True,
            score=100.0,
        )
        report = ProjectHealthReport(
            project_path=Path("/tmp/test"),
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            overall_score=100.0,
            grade="A",
            check_results=[result],
        )
        d = report.to_dict()
        assert d["project_path"] == "/tmp/test"
        assert d["timestamp"] == "2024-01-01T12:00:00"
        assert d["overall_score"] == 100.0
        assert d["grade"] == "A"
        assert len(d["check_results"]) == 1
