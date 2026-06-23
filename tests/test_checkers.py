"""Tests for pyhealth checkers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pyhealth.checkers.base import BaseChecker, CompositeChecker
from pyhealth.checkers.ci import CICDChecker
from pyhealth.checkers.code_quality import CodeQualityChecker
from pyhealth.checkers.dependencies import DependencyChecker
from pyhealth.checkers.docs import DocumentationChecker
from pyhealth.checkers.security import SecurityChecker
from pyhealth.checkers.structure import StructureChecker
from pyhealth.checkers.tests import TestsChecker
from pyhealth.models import CheckCategory, CheckResult, Issue, Severity


class TestBaseChecker:
    def test_create_issue(self) -> None:
        class TestChecker(BaseChecker):
            @property
            def name(self) -> str:
                return "Test"

            @property
            def category(self) -> CheckCategory:
                return CheckCategory.STRUCTURE

            def run(self) -> CheckResult:
                return CheckResult(
                    name="Test", category=CheckCategory.STRUCTURE, passed=True, score=100.0
                )

        checker = TestChecker(Path("/tmp"))
        issue = checker._create_issue(
            severity=Severity.WARNING,
            message="Test issue",
            file_path="test.py",
            line_number=10,
            rule_id="test-rule",
            suggestion="Fix it",
        )
        assert issue.severity == Severity.WARNING
        assert issue.message == "Test issue"
        assert issue.file_path == "test.py"
        assert issue.line_number == 10
        assert issue.rule_id == "test-rule"
        assert issue.suggestion == "Fix it"
        assert issue.category == CheckCategory.STRUCTURE

    def test_create_result(self) -> None:
        class TestChecker(BaseChecker):
            @property
            def name(self) -> str:
                return "Test"

            @property
            def category(self) -> CheckCategory:
                return CheckCategory.STRUCTURE

            def run(self) -> CheckResult:
                return CheckResult(
                    name="Test", category=CheckCategory.STRUCTURE, passed=True, score=100.0
                )

        checker = TestChecker(Path("/tmp"))
        result = checker._create_result(
            passed=True, score=90.0, issues=[], metrics={"test": "value"}
        )
        assert result.name == "Test"
        assert result.category == CheckCategory.STRUCTURE
        assert result.passed is True
        assert result.score == 90.0
        assert result.metrics["test"] == "value"


class TestCompositeChecker:
    def test_composite_checker(self) -> None:
        class MockChecker(BaseChecker):
            def __init__(self, name: str, score: float, passed: bool, category: CheckCategory):
                self._name = name
                self._score = score
                self._passed = passed
                self._category = category
                super().__init__(Path("/tmp"))

            @property
            def name(self) -> str:
                return self._name

            @property
            def category(self) -> CheckCategory:
                return self._category

            def run(self) -> CheckResult:
                return CheckResult(
                    name=self._name,
                    category=self._category,
                    passed=self._passed,
                    score=self._score,
                )

        checker1 = MockChecker("Check 1", 80.0, True, CheckCategory.DEPENDENCIES)
        checker2 = MockChecker("Check 2", 90.0, True, CheckCategory.CODE_QUALITY)
        checker3 = MockChecker("Check 3", 70.0, False, CheckCategory.SECURITY)

        composite = CompositeChecker(Path("/tmp"), checkers=[checker1, checker2, checker3])
        result = composite.run()

        assert result.name == "Composite Checker"
        assert result.category == CheckCategory.STRUCTURE
        assert result.passed is False  # One check failed
        assert result.score == 80.0  # Average of 80, 90, 70
        assert len(result.issues) == 0
        assert result.metrics["passed_checks"] == 2
        assert result.metrics["total_checks"] == 3

    def test_add_checker(self) -> None:
        class MockChecker(BaseChecker):
            @property
            def name(self) -> str:
                return "Mock"

            @property
            def category(self) -> CheckCategory:
                return CheckCategory.TESTS

            def run(self) -> CheckResult:
                return CheckResult(
                    name="Mock", category=CheckCategory.TESTS, passed=True, score=100.0
                )

        composite = CompositeChecker(Path("/tmp"))
        assert len(composite.checkers) == 0

        composite.add_checker(MockChecker(Path("/tmp")))
        assert len(composite.checkers) == 1


class TestDependencyChecker:
    @patch("subprocess.run")
    def test_check_vulnerabilities_pip_audit_not_found(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = FileNotFoundError()
        checker = DependencyChecker(Path("/tmp"))
        issues, metrics = checker._check_vulnerabilities()
        assert any(
            i.message == "pip-audit not installed, skipping vulnerability check" for i in issues
        )
        assert metrics["vulnerability_scan"] == "skipped_missing_tool"

    @patch("subprocess.run")
    def test_check_outdated_not_found(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = FileNotFoundError()
        checker = DependencyChecker(Path("/tmp"))
        issues, metrics = checker._check_outdated()
        assert metrics["outdated_check"] == "error"

    def test_check_licenses_no_license_file(self) -> None:
        checker = DependencyChecker(Path("/tmp/nonexistent"))
        issues, metrics = checker._check_licenses()
        assert any(i.rule_id == "missing-license" for i in issues)
        assert metrics["license_file_exists"] is False


class TestCodeQualityChecker:
    def test_find_ruff_config_pyproject(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[tool.ruff]")
        checker = CodeQualityChecker(tmp_path)
        config = checker._find_ruff_config()
        assert config is not None
        assert config.name == "pyproject.toml"

    def test_find_ruff_config_ruff_toml(self, tmp_path: Path) -> None:
        (tmp_path / "ruff.toml").write_text("")
        checker = CodeQualityChecker(tmp_path)
        config = checker._find_ruff_config()
        assert config is not None
        assert config.name == "ruff.toml"

    def test_find_ruff_config_none(self, tmp_path: Path) -> None:
        checker = CodeQualityChecker(tmp_path)
        config = checker._find_ruff_config()
        assert config is None


class TestSecurityChecker:
    def test_check_secrets_detects_api_key(self, tmp_path: Path) -> None:
        test_file = tmp_path / "config.py"
        test_file.write_text('API_KEY = "sk-1234567890abcdef1234567890abcdef"')
        checker = SecurityChecker(tmp_path)
        issues, metrics = checker._check_secrets()
        assert metrics["potential_secrets"] >= 1
        assert any("API Key" in i.message for i in issues)

    def test_check_security_files_gitignore_missing(self, tmp_path: Path) -> None:
        checker = SecurityChecker(tmp_path)
        issues, metrics = checker._check_security_files()
        assert any(i.rule_id == "missing-gitignore" for i in issues)
        assert metrics["has_gitignore"] is False


class TestDocumentationChecker:
    def test_check_readme_missing(self, tmp_path: Path) -> None:
        checker = DocumentationChecker(tmp_path)
        issues, metrics = checker._check_readme()
        assert any(i.rule_id == "missing-readme" for i in issues)
        assert metrics["has_readme"] is False

    def test_check_readme_exists(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text(
            "# Test Project\n\n## Installation\n\nInstall it.\n\n## Usage\n\nUse it.\n\n## License\n\nMIT"
        )
        checker = DocumentationChecker(tmp_path)
        issues, metrics = checker._check_readme()
        assert metrics["has_readme"] is True
        assert metrics["readme_has_installation"] is True
        assert metrics["readme_has_usage"] is True
        assert metrics["readme_has_license"] is True


class TestTestsChecker:
    def test_check_test_config_missing(self, tmp_path: Path) -> None:
        checker = TestsChecker(tmp_path)
        issues, metrics = checker._check_test_config()
        assert any(i.rule_id == "missing-pytest-config" for i in issues)
        assert metrics["has_pytest_config"] is False


class TestCICDChecker:
    def test_check_github_actions_missing(self, tmp_path: Path) -> None:
        checker = CICDChecker(tmp_path)
        issues, metrics = checker._check_github_actions()
        assert any(i.rule_id == "missing-github-actions" for i in issues)
        assert metrics["has_github_actions"] is False


class TestStructureChecker:
    def test_check_python_version_missing(self, tmp_path: Path) -> None:
        checker = StructureChecker(tmp_path)
        issues, metrics = checker._check_python_version()
        assert any(i.rule_id == "missing-requires-python" for i in issues)
        assert metrics["has_python_version"] is False
