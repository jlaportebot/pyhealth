"""Project structure checker for pyhealth."""

from __future__ import annotations

from typing import Any

from pyhealth.checkers.base import BaseChecker
from pyhealth.models import CheckCategory, CheckResult, Issue, Severity


class StructureChecker(BaseChecker):
    """Checks project structure: src layout, essential files, configuration."""

    @property
    def name(self) -> str:
        return "Project Structure"

    @property
    def category(self) -> CheckCategory:
        return CheckCategory.STRUCTURE

    def run(self) -> CheckResult:
        issues: list[Issue] = []
        metrics: dict[str, Any] = {}

        # Check for src layout
        src_issues, src_metrics = self._check_src_layout()
        issues.extend(src_issues)
        metrics.update(src_metrics)

        # Check for essential files
        essential_issues, essential_metrics = self._check_essential_files()
        issues.extend(essential_issues)
        metrics.update(essential_metrics)

        # Check for Python version specification
        python_issues, python_metrics = self._check_python_version()
        issues.extend(python_issues)
        metrics.update(python_metrics)

        # Check for virtual environment
        venv_issues, venv_metrics = self._check_venv()
        issues.extend(venv_issues)
        metrics.update(venv_metrics)

        # Calculate score
        error_count = len([i for i in issues if i.severity == Severity.ERROR])
        warning_count = len([i for i in issues if i.severity == Severity.WARNING])
        info_count = len([i for i in issues if i.severity == Severity.INFO])

        score = 100.0
        score -= error_count * 10
        score -= warning_count * 5
        score -= info_count * 2
        score = max(0.0, min(100.0, score))

        passed = error_count == 0

        return self._create_result(
            passed=passed,
            score=score,
            issues=issues,
            metrics=metrics,
        )

    def _check_src_layout(self) -> tuple[list[Issue], dict[str, Any]]:
        """Check for src/ layout."""
        issues: list[Issue] = []
        metrics: dict[str, Any] = {"has_src_layout": False, "has_pyproject": False}

        src_dir = self.project_path / "src"
        pyproject = self.project_path / "pyproject.toml"
        metrics["has_pyproject"] = pyproject.exists()

        if src_dir.exists() and src_dir.is_dir():
            # Check for package inside src
            pkg_dirs = [d for d in src_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]
            if pkg_dirs:
                metrics["has_src_layout"] = True
                metrics["package_dirs"] = [d.name for d in pkg_dirs]
            else:
                issues.append(
                    self._create_issue(
                        severity=Severity.WARNING,
                        message="src/ directory exists but contains no package directories",
                        file_path="src/",
                        rule_id="src-empty",
                        suggestion="Add your package directory inside src/",
                    )
                )
        else:
            # Check for flat layout (package at root)
            py_files_at_root = list(self.project_path.glob("*.py"))
            pkg_dirs_at_root = [
                d
                for d in self.project_path.iterdir()
                if d.is_dir()
                and not d.name.startswith(".")
                and d.name not in {"tests", "docs", "examples", ".git", "__pycache__"}
            ]

            if py_files_at_root or pkg_dirs_at_root:
                metrics["has_src_layout"] = False
                metrics["layout_type"] = "flat"
                issues.append(
                    self._create_issue(
                        severity=Severity.INFO,
                        message="Project uses flat layout (consider src/ layout for better isolation)",
                        rule_id="flat-layout",
                        suggestion="Consider migrating to src/ layout",
                    )
                )
            else:
                metrics["has_src_layout"] = False
                metrics["layout_type"] = "empty"

        return issues, metrics

    def _check_essential_files(self) -> tuple[list[Issue], dict[str, Any]]:
        """Check for essential project files."""
        issues: list[Issue] = []
        metrics: dict[str, Any] = {}

        essential_files = {
            "README.md": "Project documentation",
            "LICENSE": "License file",
            ".gitignore": "Git ignore rules",
            "pyproject.toml": "Project configuration",
        }

        optional_files = {
            "CHANGELOG.md": "Changelog",
            "CONTRIBUTING.md": "Contribution guidelines",
            "SECURITY.md": "Security policy",
            ".pre-commit-config.yaml": "Pre-commit hooks",
            "Makefile": "Build automation",
            "requirements.txt": "Legacy requirements",
        }

        for filename, description in essential_files.items():
            path = self.project_path / filename
            exists = path.exists()
            metrics[f"has_{filename.replace('.', '-').lower()}"] = exists
            if not exists:
                issues.append(
                    self._create_issue(
                        severity=Severity.WARNING,
                        message=f"Missing {description.lower()}: {filename}",
                        file_path=filename,
                        rule_id=f"missing-{filename.replace('.', '-')}",
                        suggestion=f"Create {filename}",
                    )
                )

        for filename, description in optional_files.items():
            path = self.project_path / filename
            exists = path.exists()
            metrics[f"has_{filename.replace('.', '-').lower()}"] = exists
            if not exists:
                issues.append(
                    self._create_issue(
                        severity=Severity.INFO,
                        message=f"Missing optional {description.lower()}: {filename}",
                        file_path=filename,
                        rule_id=f"missing-optional-{filename.replace('.', '-')}",
                        suggestion=f"Consider adding {filename}",
                    )
                )

        return issues, metrics

    def _check_python_version(self) -> tuple[list[Issue], dict[str, Any]]:
        """Check for Python version specification."""
        issues: list[Issue] = []
        metrics: dict[str, Any] = {"has_python_version": False, "python_version": None}

        pyproject = self.project_path / "pyproject.toml"
        if pyproject.exists():
            content = pyproject.read_text()
            import re

            # Check for requires-python
            match = re.search(r'requires-python\s*=\s*["\']([^"\']+)["\']', content)
            if match:
                metrics["has_python_version"] = True
                metrics["python_version"] = match.group(1)
            else:
                issues.append(
                    self._create_issue(
                        severity=Severity.WARNING,
                        message="No requires-python specified in pyproject.toml",
                        rule_id="missing-requires-python",
                        suggestion='Add requires-python = ">=3.11" to [project]',
                    )
                )
        else:
            issues.append(
                self._create_issue(
                    severity=Severity.WARNING,
                    message="No requires-python specified (pyproject.toml missing)",
                    rule_id="missing-requires-python",
                    suggestion='Add requires-python = ">=3.11" to [project]',
                )
            )

        # Check for .python-version file
        python_version_file = self.project_path / ".python-version"
        if python_version_file.exists():
            metrics["python_version_file"] = python_version_file.read_text().strip()

        return issues, metrics

    def _check_venv(self) -> tuple[list[Issue], dict[str, Any]]:
        """Check for virtual environment."""
        issues: list[Issue] = []
        metrics: dict[str, Any] = {"has_venv": False, "venv_type": None}

        venv_paths = [
            (self.project_path / ".venv", "uv/venv"),
            (self.project_path / "venv", "venv"),
            (self.project_path / "env", "env"),
        ]

        for path, vtype in venv_paths:
            if path.exists() and (path / "pyvenv.cfg").exists():
                metrics["has_venv"] = True
                metrics["venv_type"] = vtype
                metrics["venv_path"] = str(path.relative_to(self.project_path))
                break

        if not metrics["has_venv"]:
            issues.append(
                self._create_issue(
                    severity=Severity.INFO,
                    message="No virtual environment detected in project",
                    suggestion="Create a virtual environment: uv venv or python -m venv .venv",
                    rule_id="missing-venv",
                )
            )

        return issues, metrics
