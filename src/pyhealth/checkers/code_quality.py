"""Code quality checker for pyhealth."""

from __future__ import annotations

import json
import subprocess
import sys
from typing import TYPE_CHECKING, Any

from pyhealth.checkers.base import BaseChecker
from pyhealth.models import CheckCategory, CheckResult, Issue, Severity

if TYPE_CHECKING:
    from pathlib import Path


class CodeQualityChecker(BaseChecker):
    """Checks code quality: linting, formatting, type checking."""

    @property
    def name(self) -> str:
        return "Code Quality"

    @property
    def category(self) -> CheckCategory:
        return CheckCategory.CODE_QUALITY

    def run(self) -> CheckResult:
        issues: list[Issue] = []
        metrics: dict[str, Any] = {}

        # Check for configuration files
        ruff_config = self._find_ruff_config()
        pyproject = self.project_path / "pyproject.toml"
        metrics["has_pyproject"] = pyproject.exists()
        metrics["has_ruff_config"] = ruff_config is not None

        # Run ruff check
        ruff_issues, ruff_metrics = self._run_ruff()
        issues.extend(ruff_issues)
        metrics.update(ruff_metrics)

        # Run ruff format check
        format_issues, format_metrics = self._run_ruff_format()
        issues.extend(format_issues)
        metrics.update(format_metrics)

        # Run ty type check
        ty_issues, ty_metrics = self._run_ty()
        issues.extend(ty_issues)
        metrics.update(ty_metrics)

        # Calculate score
        error_count = len([i for i in issues if i.severity == Severity.ERROR])
        warning_count = len([i for i in issues if i.severity == Severity.WARNING])
        info_count = len([i for i in issues if i.severity == Severity.INFO])

        score = 100.0
        score -= error_count * 5
        score -= warning_count * 2
        score -= info_count * 1
        score = max(0.0, min(100.0, score))

        passed = error_count == 0

        return self._create_result(
            passed=passed,
            score=score,
            issues=issues,
            metrics=metrics,
        )

    def _find_ruff_config(self) -> Path | None:
        """Find ruff configuration file."""
        for name in ["ruff.toml", ".ruff.toml", "pyproject.toml"]:
            path = self.project_path / name
            if path.exists():
                return path
        return None

    def _run_ruff(self) -> tuple[list[Issue], dict[str, Any]]:
        """Run ruff check."""
        issues: list[Issue] = []
        metrics: dict[str, Any] = {"ruff_check": "skipped"}

        try:
            venv_python = self.project_path / ".venv" / "bin" / "python"
            if venv_python.exists():
                python_cmd = str(venv_python)
            else:
                python_cmd = sys.executable

            result = subprocess.run(
                [python_cmd, "-m", "ruff", "check", ".", "--output-format", "json"],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode == 0:
                metrics["ruff_check"] = "passed"
                metrics["ruff_issues"] = 0
            else:
                metrics["ruff_check"] = "issues_found"
                try:
                    data = json.loads(result.stdout)
                    metrics["ruff_issues"] = len(data)
                    for item in data:
                        filename = item.get("filename", "unknown")
                        location = item.get("location", {})
                        row = location.get("row", 0)
                        col = location.get("column", 0)
                        code = item.get("code", "unknown")
                        message = item.get("message", "Unknown issue")

                        severity = Severity.WARNING
                        if code.startswith(("E", "F")):
                            severity = Severity.ERROR

                        issues.append(
                            self._create_issue(
                                severity=severity,
                                message=f"[{code}] {message}",
                                file_path=filename,
                                line_number=row,
                                rule_id=code,
                                metadata={"column": col},
                            )
                        )
                except json.JSONDecodeError:
                    issues.append(
                        self._create_issue(
                            severity=Severity.WARNING,
                            message="ruff check ran but output could not be parsed",
                        )
                    )

        except FileNotFoundError:
            issues.append(
                self._create_issue(
                    severity=Severity.INFO,
                    message="ruff not installed, skipping lint check",
                    suggestion="Install ruff: pip install ruff",
                )
            )
            metrics["ruff_check"] = "skipped_missing_tool"
        except subprocess.TimeoutExpired:
            issues.append(
                self._create_issue(
                    severity=Severity.WARNING,
                    message="ruff check timed out",
                )
            )
            metrics["ruff_check"] = "timeout"
        except Exception as e:
            metrics["ruff_check"] = f"error: {e}"

        return issues, metrics

    def _run_ruff_format(self) -> tuple[list[Issue], dict[str, Any]]:
        """Run ruff format --check."""
        issues: list[Issue] = []
        metrics: dict[str, Any] = {"ruff_format": "skipped"}

        try:
            venv_python = self.project_path / ".venv" / "bin" / "python"
            if venv_python.exists():
                python_cmd = str(venv_python)
            else:
                python_cmd = sys.executable

            result = subprocess.run(
                [python_cmd, "-m", "ruff", "format", "--check", "."],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                metrics["ruff_format"] = "passed"
            else:
                metrics["ruff_format"] = "needs_formatting"
                issues.append(
                    self._create_issue(
                        severity=Severity.WARNING,
                        message="Code formatting issues found (run 'ruff format .' to fix)",
                        rule_id="format",
                        suggestion="Run 'ruff format .' to auto-format",
                    )
                )

        except FileNotFoundError:
            metrics["ruff_format"] = "skipped_missing_tool"
        except Exception as e:
            metrics["ruff_format"] = f"error: {e}"

        return issues, metrics

    def _run_ty(self) -> tuple[list[Issue], dict[str, Any]]:
        """Run ty type checker."""
        issues: list[Issue] = []
        metrics: dict[str, Any] = {"ty_check": "skipped"}

        # Only run if pyproject.toml exists
        if not (self.project_path / "pyproject.toml").exists():
            return issues, metrics

        try:
            venv_python = self.project_path / ".venv" / "bin" / "python"
            if venv_python.exists():
                python_cmd = str(venv_python)
            else:
                python_cmd = sys.executable

            result = subprocess.run(
                [python_cmd, "-m", "ty", "check", "src"],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode == 0:
                metrics["ty_check"] = "passed"
            else:
                metrics["ty_check"] = "issues_found"
                # Parse ty output (simplified)
                for line in result.stdout.strip().split("\n"):
                    if line and ("error:" in line or "warning:" in line):
                        severity = Severity.ERROR if "error:" in line else Severity.WARNING
                        issues.append(
                            self._create_issue(
                                severity=severity,
                                message=line.strip(),
                                rule_id="ty-type-check",
                            )
                        )

        except FileNotFoundError:
            issues.append(
                self._create_issue(
                    severity=Severity.INFO,
                    message="ty not installed, skipping type check",
                    suggestion="Install ty: pip install ty",
                )
            )
            metrics["ty_check"] = "skipped_missing_tool"
        except subprocess.TimeoutExpired:
            metrics["ty_check"] = "timeout"
        except Exception as e:
            metrics["ty_check"] = f"error: {e}"

        return issues, metrics
