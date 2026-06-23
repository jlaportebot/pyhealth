"""Dependency health checker for pyhealth."""

from __future__ import annotations

import json
import subprocess
import sys
from typing import Any

from pyhealth.checkers.base import BaseChecker
from pyhealth.models import CheckCategory, CheckResult, Issue, Severity


class DependencyChecker(BaseChecker):
    """Checks dependency health: vulnerabilities, outdated packages, licenses."""

    @property
    def name(self) -> str:
        return "Dependency Health"

    @property
    def category(self) -> CheckCategory:
        return CheckCategory.DEPENDENCIES

    def run(self) -> CheckResult:
        issues: list[Issue] = []
        metrics: dict[str, Any] = {}

        # Check for pyproject.toml or requirements files
        pyproject_path = self.project_path / "pyproject.toml"
        req_files = list(self.project_path.glob("requirements*.txt"))
        req_files.append(self.project_path / "requirements.txt")

        has_dep_file = pyproject_path.exists() or any(f.exists() for f in req_files)

        if not has_dep_file:
            issues.append(
                self._create_issue(
                    severity=Severity.WARNING,
                    message="No dependency configuration file found (pyproject.toml, requirements.txt)",
                    suggestion="Add a pyproject.toml or requirements.txt to manage dependencies",
                )
            )
            return self._create_result(
                passed=False,
                score=30.0,
                issues=issues,
                metrics={"has_dep_file": False},
            )

        metrics["has_dep_file"] = True
        metrics["pyproject_exists"] = pyproject_path.exists()
        metrics["requirements_files"] = [
            str(f.relative_to(self.project_path)) for f in req_files if f.exists()
        ]

        # Run pip-audit for vulnerabilities
        vuln_issues, vuln_metrics = self._check_vulnerabilities()
        issues.extend(vuln_issues)
        metrics.update(vuln_metrics)

        # Check for outdated packages
        outdated_issues, outdated_metrics = self._check_outdated()
        issues.extend(outdated_issues)
        metrics.update(outdated_metrics)

        # Check license compliance (basic)
        license_issues, license_metrics = self._check_licenses()
        issues.extend(license_issues)
        metrics.update(license_metrics)

        # Calculate score
        critical_count = len([i for i in issues if i.severity == Severity.CRITICAL])
        error_count = len([i for i in issues if i.severity == Severity.ERROR])
        warning_count = len([i for i in issues if i.severity == Severity.WARNING])

        score = 100.0
        score -= critical_count * 25
        score -= error_count * 10
        score -= warning_count * 5
        score = max(0.0, min(100.0, score))

        passed = critical_count == 0 and error_count == 0

        return self._create_result(
            passed=passed,
            score=score,
            issues=issues,
            metrics=metrics,
        )

    def _check_vulnerabilities(self) -> tuple[list[Issue], dict[str, Any]]:
        """Run pip-audit to check for vulnerabilities."""
        issues: list[Issue] = []
        metrics: dict[str, Any] = {"vulnerabilities_found": 0, "vulnerability_scan": "skipped"}

        try:
            # Run pip-audit in the project's virtual environment if available
            venv_python = self.project_path / ".venv" / "bin" / "python"
            if venv_python.exists():
                python_cmd = str(venv_python)
            else:
                python_cmd = sys.executable

            result = subprocess.run(
                [python_cmd, "-m", "pip_audit", "--format", "json"],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode == 0:
                metrics["vulnerability_scan"] = "passed"
                metrics["vulnerabilities_found"] = 0
            else:
                metrics["vulnerability_scan"] = "completed_with_findings"
                try:
                    data = json.loads(result.stdout)
                    vulns = data.get("vulnerabilities", [])
                    metrics["vulnerabilities_found"] = len(vulns)

                    for vuln in vulns:
                        pkg = vuln.get("package", "unknown")
                        version = vuln.get("installed_version", "unknown")
                        vuln_id = vuln.get("id", "unknown")
                        description = vuln.get("description", "No description")
                        fix_versions = vuln.get("fix_versions", [])

                        suggestion = None
                        if fix_versions:
                            suggestion = f"Upgrade to {fix_versions[0]} or later"

                        issues.append(
                            self._create_issue(
                                severity=Severity.CRITICAL,
                                message=f"Vulnerability {vuln_id} in {pkg}=={version}: {description}",
                                rule_id=vuln_id,
                                suggestion=suggestion,
                                metadata={
                                    "package": pkg,
                                    "version": version,
                                    "fix_versions": fix_versions,
                                },
                            )
                        )
                except json.JSONDecodeError:
                    issues.append(
                        self._create_issue(
                            severity=Severity.WARNING,
                            message="pip-audit ran but output could not be parsed",
                        )
                    )

        except FileNotFoundError:
            issues.append(
                self._create_issue(
                    severity=Severity.INFO,
                    message="pip-audit not installed, skipping vulnerability check",
                    suggestion="Install pip-audit: pip install pip-audit",
                )
            )
            metrics["vulnerability_scan"] = "skipped_missing_tool"
        except subprocess.TimeoutExpired:
            issues.append(
                self._create_issue(
                    severity=Severity.WARNING,
                    message="Vulnerability scan timed out",
                )
            )
            metrics["vulnerability_scan"] = "timeout"
        except Exception as e:
            issues.append(
                self._create_issue(
                    severity=Severity.WARNING,
                    message=f"Vulnerability scan failed: {e}",
                )
            )
            metrics["vulnerability_scan"] = f"error: {e}"

        return issues, metrics

    def _check_outdated(self) -> tuple[list[Issue], dict[str, Any]]:
        """Check for outdated packages using pip list --outdated."""
        issues: list[Issue] = []
        metrics: dict[str, Any] = {"outdated_packages": 0, "outdated_check": "skipped"}

        try:
            venv_python = self.project_path / ".venv" / "bin" / "python"
            if venv_python.exists():
                python_cmd = str(venv_python)
            else:
                python_cmd = sys.executable

            result = subprocess.run(
                [python_cmd, "-m", "pip", "list", "--outdated", "--format", "json"],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                try:
                    outdated = json.loads(result.stdout)
                    metrics["outdated_packages"] = len(outdated)
                    metrics["outdated_check"] = "completed"

                    if outdated:
                        for pkg in outdated[:10]:  # Limit to top 10
                            name = pkg.get("name", "unknown")
                            current = pkg.get("version", "unknown")
                            latest = pkg.get("latest_version", "unknown")
                            issues.append(
                                self._create_issue(
                                    severity=Severity.WARNING,
                                    message=f"Outdated package: {name}=={current} (latest: {latest})",
                                    rule_id="outdated-package",
                                    suggestion=f"Upgrade {name} to {latest}",
                                    metadata={
                                        "package": name,
                                        "current": current,
                                        "latest": latest,
                                    },
                                )
                            )
                        if len(outdated) > 10:
                            issues.append(
                                self._create_issue(
                                    severity=Severity.INFO,
                                    message=f"... and {len(outdated) - 10} more outdated packages",
                                    rule_id="outdated-package",
                                )
                            )
                except json.JSONDecodeError:
                    metrics["outdated_check"] = "parse_error"
        except Exception:
            metrics["outdated_check"] = "error"

        return issues, metrics

    def _check_licenses(self) -> tuple[list[Issue], dict[str, Any]]:
        """Basic license check - look for license files."""
        issues: list[Issue] = []
        metrics: dict[str, Any] = {"license_file_exists": False}

        license_files = [
            "LICENSE",
            "LICENSE.txt",
            "LICENSE.md",
            "COPYING",
            "COPYING.txt",
            "COPYING.md",
        ]

        for lf in license_files:
            if (self.project_path / lf).exists():
                metrics["license_file_exists"] = True
                metrics["license_file"] = lf
                break

        if not metrics["license_file_exists"]:
            issues.append(
                self._create_issue(
                    severity=Severity.WARNING,
                    message="No license file found in project root",
                    suggestion="Add a LICENSE file (MIT, Apache-2.0, etc.)",
                    rule_id="missing-license",
                )
            )

        return issues, metrics
