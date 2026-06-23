"""CI/CD checker for pyhealth."""

from __future__ import annotations

from typing import Any

from pyhealth.checkers.base import BaseChecker
from pyhealth.models import CheckCategory, CheckResult, Issue, Severity


class CICDChecker(BaseChecker):
    """Checks CI/CD configuration: GitHub Actions, GitLab CI, etc."""

    @property
    def name(self) -> str:
        return "CI/CD Configuration"

    @property
    def category(self) -> CheckCategory:
        return CheckCategory.CI_CD

    def run(self) -> CheckResult:
        issues: list[Issue] = []
        metrics: dict[str, Any] = {}

        # Check for GitHub Actions workflows
        gh_issues, gh_metrics = self._check_github_actions()
        issues.extend(gh_issues)
        metrics.update(gh_metrics)

        # Check for other CI configs
        other_ci_issues, other_ci_metrics = self._check_other_ci()
        issues.extend(other_ci_issues)
        metrics.update(other_ci_metrics)

        # Check for pre-commit config
        precommit_issues, precommit_metrics = self._check_precommit()
        issues.extend(precommit_issues)
        metrics.update(precommit_metrics)

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

    def _check_github_actions(self) -> tuple[list[Issue], dict[str, Any]]:
        """Check for GitHub Actions workflows."""
        issues: list[Issue] = []
        metrics: dict[str, Any] = {
            "has_github_actions": False,
            "workflow_count": 0,
            "has_ci_workflow": False,
            "has_cd_workflow": False,
        }

        workflows_dir = self.project_path / ".github" / "workflows"
        if workflows_dir.exists() and workflows_dir.is_dir():
            workflow_files = list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml"))
            metrics["has_github_actions"] = True
            metrics["workflow_count"] = len(workflow_files)
            metrics["workflow_files"] = [f.name for f in workflow_files]

            for wf in workflow_files:
                try:
                    content = wf.read_text()
                    if "on:" in content:
                        if "push:" in content or "pull_request:" in content:
                            metrics["has_ci_workflow"] = True
                        if "release:" in content or "workflow_dispatch:" in content:
                            metrics["has_cd_workflow"] = True

                    # Check for common best practices
                    if "actions/checkout" not in content:
                        issues.append(
                            self._create_issue(
                                severity=Severity.INFO,
                                message=f"Workflow {wf.name} may be missing actions/checkout",
                                file_path=str(wf.relative_to(self.project_path)),
                                rule_id="gha-missing-checkout",
                            )
                        )

                    if "permissions:" not in content:
                        issues.append(
                            self._create_issue(
                                severity=Severity.INFO,
                                message=f"Workflow {wf.name} missing explicit permissions",
                                file_path=str(wf.relative_to(self.project_path)),
                                rule_id="gha-missing-permissions",
                                suggestion="Add explicit permissions: contents: read, etc.",
                            )
                        )

                except Exception:
                    pass

            if not metrics["has_ci_workflow"]:
                issues.append(
                    self._create_issue(
                        severity=Severity.WARNING,
                        message="No CI workflow found (push/pull_request triggers)",
                        rule_id="gha-missing-ci",
                        suggestion="Add a CI workflow that runs on push and pull_request",
                    )
                )
        else:
            issues.append(
                self._create_issue(
                    severity=Severity.WARNING,
                    message="No GitHub Actions workflows found",
                    suggestion="Add CI/CD workflows in .github/workflows/",
                    rule_id="missing-github-actions",
                )
            )

        return issues, metrics

    def _check_other_ci(self) -> tuple[list[Issue], dict[str, Any]]:
        """Check for other CI configuration files."""
        issues: list[Issue] = []
        metrics: dict[str, Any] = {}

        ci_files = {
            ".gitlab-ci.yml": "GitLab CI",
            ".circleci/config.yml": "CircleCI",
            "azure-pipelines.yml": "Azure Pipelines",
            "Jenkinsfile": "Jenkins",
            ".travis.yml": "Travis CI",
            "bitbucket-pipelines.yml": "Bitbucket Pipelines",
        }

        found_ci = []
        for ci_file, ci_name in ci_files.items():
            if (self.project_path / ci_file).exists():
                found_ci.append(ci_name)

        metrics["other_ci_systems"] = found_ci

        return issues, metrics

    def _check_precommit(self) -> tuple[list[Issue], dict[str, Any]]:
        """Check for pre-commit configuration."""
        issues: list[Issue] = []
        metrics: dict[str, Any] = {"has_precommit": False, "hook_count": 0}

        precommit_file = self.project_path / ".pre-commit-config.yaml"
        if precommit_file.exists():
            metrics["has_precommit"] = True
            try:
                import yaml

                content = yaml.safe_load(precommit_file.read_text())
                if content and "repos" in content:
                    hook_count = sum(len(repo.get("hooks", [])) for repo in content["repos"])
                    metrics["hook_count"] = hook_count
            except Exception:
                pass
        else:
            issues.append(
                self._create_issue(
                    severity=Severity.INFO,
                    message="No pre-commit configuration found",
                    suggestion="Add .pre-commit-config.yaml for automated code quality checks",
                    rule_id="missing-precommit",
                )
            )

        return issues, metrics
