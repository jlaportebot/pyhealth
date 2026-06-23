"""Tests checker for pyhealth."""

from __future__ import annotations

import subprocess
import sys
from typing import Any

from pyhealth.checkers.base import BaseChecker
from pyhealth.models import CheckCategory, CheckResult, Issue, Severity


class TestsChecker(BaseChecker):
    """Checks test coverage, quality, and configuration."""

    @property
    def name(self) -> str:
        return "Tests"

    @property
    def category(self) -> CheckCategory:
        return CheckCategory.TESTS

    def run(self) -> CheckResult:
        issues: list[Issue] = []
        metrics: dict[str, Any] = {}

        # Check for test directory
        tests_dir = self.project_path / "tests"
        metrics["has_tests_dir"] = tests_dir.exists()
        metrics["test_file_count"] = 0

        if not tests_dir.exists():
            issues.append(
                self._create_issue(
                    severity=Severity.WARNING,
                    message="No tests directory found",
                    suggestion="Create a tests/ directory with test files",
                    rule_id="missing-tests-dir",
                )
            )
        else:
            test_files = list(tests_dir.rglob("test_*.py")) + list(tests_dir.rglob("*_test.py"))
            metrics["test_file_count"] = len(test_files)
            if len(test_files) == 0:
                issues.append(
                    self._create_issue(
                        severity=Severity.WARNING,
                        message="Tests directory exists but contains no test files",
                        suggestion="Add test files named test_*.py or *_test.py",
                        rule_id="empty-tests-dir",
                    )
                )

        # Run pytest with coverage
        pytest_issues, pytest_metrics = self._run_pytest()
        issues.extend(pytest_issues)
        metrics.update(pytest_metrics)

        # Check for test configuration
        config_issues, config_metrics = self._check_test_config()
        issues.extend(config_issues)
        metrics.update(config_metrics)

        # Calculate score
        error_count = len([i for i in issues if i.severity == Severity.ERROR])
        warning_count = len([i for i in issues if i.severity == Severity.WARNING])

        score = 100.0
        if metrics.get("coverage", 0) > 0:
            score = metrics["coverage"]
        score -= error_count * 10
        score -= warning_count * 5
        score = max(0.0, min(100.0, score))

        passed = error_count == 0 and metrics.get("tests_passed", False)

        return self._create_result(
            passed=passed,
            score=score,
            issues=issues,
            metrics=metrics,
        )

    def _run_pytest(self) -> tuple[list[Issue], dict[str, Any]]:
        """Run pytest with coverage."""
        issues: list[Issue] = []
        metrics: dict[str, Any] = {"pytest_run": "skipped", "tests_passed": False, "coverage": 0.0}

        tests_dir = self.project_path / "tests"
        if not tests_dir.exists():
            return issues, metrics

        try:
            venv_python = self.project_path / ".venv" / "bin" / "python"
            if venv_python.exists():
                python_cmd = str(venv_python)
            else:
                python_cmd = sys.executable

            result = subprocess.run(
                [python_cmd, "-m", "pytest", "--cov=.", "--cov-report=term-missing", "-q"],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode == 0:
                metrics["pytest_run"] = "passed"
                metrics["tests_passed"] = True
            else:
                metrics["pytest_run"] = "failed"
                metrics["tests_passed"] = False
                # Parse output for failures
                for line in result.stdout.strip().split("\n"):
                    if "FAILED" in line or "ERROR" in line:
                        issues.append(
                            self._create_issue(
                                severity=Severity.ERROR,
                                message=line.strip(),
                                rule_id="test-failure",
                            )
                        )

            # Extract coverage from output
            import re

            coverage_match = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", result.stdout)
            if coverage_match:
                metrics["coverage"] = float(coverage_match.group(1))
            else:
                # Try alternative format
                coverage_match = re.search(r"(\d+)% coverage", result.stdout)
                if coverage_match:
                    metrics["coverage"] = float(coverage_match.group(1))

            if metrics["coverage"] < 70:
                issues.append(
                    self._create_issue(
                        severity=Severity.WARNING,
                        message=f"Test coverage is {metrics['coverage']:.1f}% (recommended: >=70%)",
                        rule_id="low-coverage",
                        suggestion="Add more tests to improve coverage",
                        metadata={"coverage": metrics["coverage"]},
                    )
                )

        except subprocess.TimeoutExpired:
            metrics["pytest_run"] = "timeout"
            issues.append(
                self._create_issue(
                    severity=Severity.ERROR,
                    message="Test run timed out",
                    rule_id="test-timeout",
                )
            )
        except Exception as e:
            metrics["pytest_run"] = f"error: {e}"

        return issues, metrics

    def _check_test_config(self) -> tuple[list[Issue], dict[str, Any]]:
        """Check for test configuration in pyproject.toml."""
        issues: list[Issue] = []
        metrics: dict[str, Any] = {"has_pytest_config": False}

        pyproject = self.project_path / "pyproject.toml"
        if pyproject.exists():
            content = pyproject.read_text()
            if "[tool.pytest" in content or "pytest.ini" in content or "addopts" in content:
                metrics["has_pytest_config"] = True
            else:
                issues.append(
                    self._create_issue(
                        severity=Severity.INFO,
                        message="No pytest configuration found in pyproject.toml",
                        suggestion="Add [tool.pytest.ini_options] to pyproject.toml",
                        rule_id="missing-pytest-config",
                    )
                )
        else:
            issues.append(
                self._create_issue(
                    severity=Severity.INFO,
                    message="No pytest configuration found (pyproject.toml missing)",
                    suggestion="Add [tool.pytest.ini_options] to pyproject.toml",
                    rule_id="missing-pytest-config",
                )
            )

        return issues, metrics
