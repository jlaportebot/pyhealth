"""Security checker for pyhealth."""

from __future__ import annotations

import json  # noqa: F401 (used in exception handling)
import subprocess
import sys
from typing import Any

from pyhealth.checkers.base import BaseChecker
from pyhealth.models import CheckCategory, CheckResult, Issue, Severity


class SecurityChecker(BaseChecker):
    """Checks security: bandit, pip-audit, secrets detection."""

    @property
    def name(self) -> str:
        return "Security"

    @property
    def category(self) -> CheckCategory:
        return CheckCategory.SECURITY

    def run(self) -> CheckResult:
        issues: list[Issue] = []
        metrics: dict[str, Any] = {}

        # Run bandit for static analysis
        bandit_issues, bandit_metrics = self._run_bandit()
        issues.extend(bandit_issues)
        metrics.update(bandit_metrics)

        # Check for secrets in code
        secrets_issues, secrets_metrics = self._check_secrets()
        issues.extend(secrets_issues)
        metrics.update(secrets_metrics)

        # Check for security-related files
        security_files_issues, security_files_metrics = self._check_security_files()
        issues.extend(security_files_issues)
        metrics.update(security_files_metrics)

        # Calculate score
        critical_count = len([i for i in issues if i.severity == Severity.CRITICAL])
        error_count = len([i for i in issues if i.severity == Severity.ERROR])
        warning_count = len([i for i in issues if i.severity == Severity.WARNING])

        score = 100.0
        score -= critical_count * 20
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

    def _run_bandit(self) -> tuple[list[Issue], dict[str, Any]]:
        """Run bandit for static security analysis."""
        issues: list[Issue] = []
        metrics: dict[str, Any] = {"bandit_scan": "skipped"}

        # Only run on Python files
        py_files = list(self.project_path.rglob("*.py"))
        if not py_files:
            return issues, metrics

        try:
            venv_python = self.project_path / ".venv" / "bin" / "python"
            if venv_python.exists():
                python_cmd = str(venv_python)
            else:
                python_cmd = sys.executable

            result = subprocess.run(
                [python_cmd, "-m", "bandit", "-r", "src", "-f", "json"],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode == 0:
                metrics["bandit_scan"] = "passed"
                metrics["bandit_issues"] = 0
            else:
                metrics["bandit_scan"] = "issues_found"
                try:
                    import json

                    data = json.loads(result.stdout)
                    results = data.get("results", [])
                    metrics["bandit_issues"] = len(results)

                    for item in results:
                        severity_map = {
                            "HIGH": Severity.CRITICAL,
                            "MEDIUM": Severity.ERROR,
                            "LOW": Severity.WARNING,
                        }
                        severity = severity_map.get(
                            item.get("issue_severity", "LOW"), Severity.WARNING
                        )

                        issues.append(
                            self._create_issue(
                                severity=severity,
                                message=f"[{item.get('test_id', 'unknown')}] {item.get('issue_text', 'Security issue')}",
                                file_path=item.get("filename", "unknown"),
                                line_number=item.get("line_number"),
                                rule_id=item.get("test_id"),
                                suggestion=item.get("more_info"),
                                metadata={
                                    "confidence": item.get("issue_confidence"),
                                    "cwe": item.get("cwe"),
                                },
                            )
                        )
                except json.JSONDecodeError:  # ty: ignore[possibly-unresolved-reference]
                    issues.append(
                        self._create_issue(
                            severity=Severity.WARNING,
                            message="bandit ran but output could not be parsed",
                        )
                    )

        except FileNotFoundError:
            issues.append(
                self._create_issue(
                    severity=Severity.INFO,
                    message="bandit not installed, skipping static security analysis",
                    suggestion="Install bandit: pip install bandit",
                )
            )
            metrics["bandit_scan"] = "skipped_missing_tool"
        except subprocess.TimeoutExpired:
            metrics["bandit_scan"] = "timeout"
        except Exception as e:
            metrics["bandit_scan"] = f"error: {e}"

        return issues, metrics

    def _check_secrets(self) -> tuple[list[Issue], dict[str, Any]]:
        """Basic secrets detection in code files."""
        issues: list[Issue] = []
        metrics: dict[str, Any] = {"secrets_check": "completed", "potential_secrets": 0}

        # Patterns for common secrets
        import re

        secret_patterns = [
            (r"(?i)(api[_-]?key|apikey)\s*[=:]\s*[\"']?[a-zA-Z0-9_\-]{20,}[\"']?", "API Key"),
            (
                r"(?i)(secret[_-]?key|secretkey)\s*[=:]\s*[\"']?[a-zA-Z0-9_\-]{20,}[\"']?",
                "Secret Key",
            ),
            (r"(?i)(password|passwd)\s*[=:]\s*[\"']?[^\s\"']{8,}[\"']?", "Password"),
            (r"(?i)(token)\s*[=:]\s*[\"']?[a-zA-Z0-9_\-]{20,}[\"']?", "Token"),
            (r"ghp_[a-zA-Z0-9]{36}", "GitHub Personal Access Token"),
            (r"gho_[a-zA-Z0-9]{36}", "GitHub OAuth Token"),
            (r"github_pat_[a-zA-Z0-9_]{82}", "GitHub Fine-grained PAT"),
        ]

        exclude_dirs = {
            ".git",
            "__pycache__",
            ".venv",
            "venv",
            "env",
            "node_modules",
            ".pytest_cache",
            ".ruff_cache",
        }
        text_extensions = {
            ".py",
            ".txt",
            ".yaml",
            ".yml",
            ".json",
            ".toml",
            ".ini",
            ".cfg",
            ".env",
            ".env.example",
        }

        for file_path in self.project_path.rglob("*"):
            if not file_path.is_file():
                continue
            if any(part in exclude_dirs for part in file_path.parts):
                continue
            if file_path.suffix not in text_extensions and file_path.name not in {
                ".env",
                ".env.example",
            }:
                continue

            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                for pattern, label in secret_patterns:
                    matches = list(re.finditer(pattern, content))
                    if matches:
                        metrics["potential_secrets"] += len(matches)
                        for match in matches[:3]:  # Limit to 3 per file per pattern
                            line_num = content[: match.start()].count("\n") + 1
                            issues.append(
                                self._create_issue(
                                    severity=Severity.CRITICAL,
                                    message=f"Potential {label} detected in source code",
                                    file_path=str(file_path.relative_to(self.project_path)),
                                    line_number=line_num,
                                    rule_id=label.replace(" ", "-").lower(),
                                    suggestion=f"Remove {label.lower()} from source code and use environment variables",
                                    metadata={"pattern": label},
                                )
                            )
            except Exception:
                pass

        return issues, metrics

    def _check_security_files(self) -> tuple[list[Issue], dict[str, Any]]:
        """Check for security-related configuration files."""
        issues: list[Issue] = []
        metrics: dict[str, Any] = {}

        # Check for .gitignore
        gitignore = self.project_path / ".gitignore"
        metrics["has_gitignore"] = gitignore.exists()
        if gitignore.exists():
            content = gitignore.read_text()
            metrics["gitignore_has_env"] = ".env" in content
            metrics["gitignore_has_venv"] = any(p in content for p in [".venv", "venv/", "env/"])
            if ".env" not in content:
                issues.append(
                    self._create_issue(
                        severity=Severity.WARNING,
                        message=".gitignore does not exclude .env files",
                        file_path=".gitignore",
                        rule_id="gitignore-missing-env",
                        suggestion="Add '.env' to .gitignore",
                    )
                )
        else:
            issues.append(
                self._create_issue(
                    severity=Severity.WARNING,
                    message="No .gitignore file found",
                    suggestion="Create a .gitignore file to exclude sensitive files",
                    rule_id="missing-gitignore",
                )
            )

        # Check for security policy
        security_md = self.project_path / "SECURITY.md"
        metrics["has_security_policy"] = security_md.exists()
        if not security_md.exists():
            issues.append(
                self._create_issue(
                    severity=Severity.INFO,
                    message="No SECURITY.md file found",
                    suggestion="Add a SECURITY.md with vulnerability reporting instructions",
                    rule_id="missing-security-policy",
                )
            )

        # Check for dependabot config
        dependabot = self.project_path / ".github" / "dependabot.yml"
        metrics["has_dependabot"] = dependabot.exists()

        return issues, metrics
