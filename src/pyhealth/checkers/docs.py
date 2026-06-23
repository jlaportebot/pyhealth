"""Documentation checker for pyhealth."""

from __future__ import annotations

from typing import Any

from pyhealth.checkers.base import BaseChecker
from pyhealth.models import CheckCategory, CheckResult, Issue, Severity


class DocumentationChecker(BaseChecker):
    """Checks documentation: README, docstrings, type hints, examples."""

    @property
    def name(self) -> str:
        return "Documentation"

    @property
    def category(self) -> CheckCategory:
        return CheckCategory.DOCUMENTATION

    def run(self) -> CheckResult:
        issues: list[Issue] = []
        metrics: dict[str, Any] = {}

        # Check for README
        readme_issues, readme_metrics = self._check_readme()
        issues.extend(readme_issues)
        metrics.update(readme_metrics)

        # Check for docstrings in Python files
        docstring_issues, docstring_metrics = self._check_docstrings()
        issues.extend(docstring_issues)
        metrics.update(docstring_metrics)

        # Check for type hints
        type_hint_issues, type_hint_metrics = self._check_type_hints()
        issues.extend(type_hint_issues)
        metrics.update(type_hint_metrics)

        # Check for examples directory
        examples_issues, examples_metrics = self._check_examples()
        issues.extend(examples_issues)
        metrics.update(examples_metrics)

        # Check for CHANGELOG
        changelog_issues, changelog_metrics = self._check_changelog()
        issues.extend(changelog_issues)
        metrics.update(changelog_metrics)

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

    def _check_readme(self) -> tuple[list[Issue], dict[str, Any]]:
        """Check for README file and content."""
        issues: list[Issue] = []
        metrics: dict[str, Any] = {"has_readme": False, "readme_size": 0}

        readme_files = [
            "README.md",
            "README.rst",
            "README.txt",
            "README",
        ]

        readme_path = None
        for rf in readme_files:
            path = self.project_path / rf
            if path.exists():
                readme_path = path
                break

        if readme_path:
            metrics["has_readme"] = True
            metrics["readme_file"] = readme_path.name
            content = readme_path.read_text()
            metrics["readme_size"] = len(content)
            metrics["readme_lines"] = len(content.splitlines())

            # Check for key sections
            sections = [
                ("installation", ["install", "getting started", "setup"]),
                ("usage", ["usage", "example", "quickstart"]),
                ("license", ["license", "licence"]),
                ("contributing", ["contributing", "contribute"]),
            ]

            content_lower = content.lower()
            for section, keywords in sections:
                found = any(kw in content_lower for kw in keywords)
                metrics[f"readme_has_{section}"] = found
                if not found:
                    issues.append(
                        self._create_issue(
                            severity=Severity.INFO,
                            message=f"README missing '{section}' section",
                            file_path=readme_path.name,
                            rule_id=f"readme-missing-{section}",
                            suggestion=f"Add a {section.capitalize()} section to README",
                        )
                    )
        else:
            issues.append(
                self._create_issue(
                    severity=Severity.WARNING,
                    message="No README file found",
                    suggestion="Create a README.md with project description, installation, and usage",
                    rule_id="missing-readme",
                )
            )

        return issues, metrics

    def _check_docstrings(self) -> tuple[list[Issue], dict[str, Any]]:
        """Check for docstrings in Python modules and functions."""
        issues: list[Issue] = []
        metrics: dict[str, Any] = {
            "modules_checked": 0,
            "modules_with_docstring": 0,
            "functions_checked": 0,
            "functions_with_docstring": 0,
        }

        src_dirs = ["src", "."]
        py_files = []
        for src_dir in src_dirs:
            path = self.project_path / src_dir
            if path.exists():
                py_files.extend(path.rglob("*.py"))

        for py_file in py_files:
            if any(part in {".venv", "venv", "__pycache__", ".git"} for part in py_file.parts):
                continue

            try:
                content = py_file.read_text()
                lines = content.splitlines()

                # Check module docstring
                metrics["modules_checked"] += 1
                if lines and (
                    lines[0].strip().startswith('"""') or lines[0].strip().startswith("'''")
                ):
                    metrics["modules_with_docstring"] += 1
                else:
                    issues.append(
                        self._create_issue(
                            severity=Severity.INFO,
                            message="Module missing docstring",
                            file_path=str(py_file.relative_to(self.project_path)),
                            line_number=1,
                            rule_id="missing-module-docstring",
                            suggestion="Add a module-level docstring",
                        )
                    )

                # Check function/class docstrings (simplified)
                for i, line in enumerate(lines):
                    stripped = line.strip()
                    if stripped.startswith(("def ", "class ")):
                        metrics["functions_checked"] += 1
                        # Check next non-empty line for docstring
                        for j in range(i + 1, min(i + 5, len(lines))):
                            next_line = lines[j].strip()
                            if next_line and not next_line.startswith("#"):
                                if next_line.startswith(('"""', "'''")):
                                    metrics["functions_with_docstring"] += 1
                                break
            except Exception:
                pass

        if metrics["functions_checked"] > 0:
            docstring_ratio = metrics["functions_with_docstring"] / metrics["functions_checked"]
            metrics["docstring_coverage"] = round(docstring_ratio * 100, 1)
            if docstring_ratio < 0.5:
                issues.append(
                    self._create_issue(
                        severity=Severity.WARNING,
                        message=f"Low docstring coverage: {metrics['docstring_coverage']}% of functions/classes documented",
                        rule_id="low-docstring-coverage",
                        suggestion="Add docstrings to public functions and classes",
                    )
                )

        return issues, metrics

    def _check_type_hints(self) -> tuple[list[Issue], dict[str, Any]]:
        """Check for type hints in Python files."""
        issues: list[Issue] = []
        metrics: dict[str, Any] = {"functions_checked": 0, "functions_with_type_hints": 0}

        src_dirs = ["src", "."]
        py_files = []
        for src_dir in src_dirs:
            path = self.project_path / src_dir
            if path.exists():
                py_files.extend(path.rglob("*.py"))

        for py_file in py_files:
            if any(part in {".venv", "venv", "__pycache__", ".git"} for part in py_file.parts):
                continue

            try:
                content = py_file.read_text()
                lines = content.splitlines()

                for line in lines:
                    stripped = line.strip()
                    if stripped.startswith("def ") and not stripped.startswith("def __"):
                        metrics["functions_checked"] += 1
                        # Simple check for type hints
                        if (
                            "->" in line
                            or ": " in line.split("def ")[1].split("(")[1].split(")")[0]
                        ):
                            metrics["functions_with_type_hints"] += 1
            except Exception:
                pass

        if metrics["functions_checked"] > 0:
            type_hint_ratio = metrics["functions_with_type_hints"] / metrics["functions_checked"]
            metrics["type_hint_coverage"] = round(type_hint_ratio * 100, 1)
            if type_hint_ratio < 0.5:
                issues.append(
                    self._create_issue(
                        severity=Severity.INFO,
                        message=f"Low type hint coverage: {metrics['type_hint_coverage']}% of functions have type hints",
                        rule_id="low-type-hint-coverage",
                        suggestion="Add type hints to function signatures",
                    )
                )

        return issues, metrics

    def _check_examples(self) -> tuple[list[Issue], dict[str, Any]]:
        """Check for examples directory."""
        issues: list[Issue] = []
        metrics: dict[str, Any] = {"has_examples_dir": False, "example_count": 0}

        examples_dir = self.project_path / "examples"
        if examples_dir.exists() and examples_dir.is_dir():
            metrics["has_examples_dir"] = True
            example_files = list(examples_dir.rglob("*.py")) + list(examples_dir.rglob("*.ipynb"))
            metrics["example_count"] = len(example_files)
        else:
            issues.append(
                self._create_issue(
                    severity=Severity.INFO,
                    message="No examples directory found",
                    suggestion="Add an examples/ directory with usage examples",
                    rule_id="missing-examples",
                )
            )

        return issues, metrics

    def _check_changelog(self) -> tuple[list[Issue], dict[str, Any]]:
        """Check for CHANGELOG file."""
        issues: list[Issue] = []
        metrics: dict[str, Any] = {"has_changelog": False}

        changelog_files = [
            "CHANGELOG.md",
            "CHANGELOG.rst",
            "CHANGELOG.txt",
            "CHANGES.md",
            "HISTORY.md",
            "RELEASES.md",
        ]

        for cf in changelog_files:
            if (self.project_path / cf).exists():
                metrics["has_changelog"] = True
                metrics["changelog_file"] = cf
                break

        if not metrics["has_changelog"]:
            issues.append(
                self._create_issue(
                    severity=Severity.INFO,
                    message="No CHANGELOG file found",
                    suggestion="Add a CHANGELOG.md following Keep a Changelog format",
                    rule_id="missing-changelog",
                )
            )

        return issues, metrics
