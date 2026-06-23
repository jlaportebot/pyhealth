"""Base checker classes for pyhealth."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Callable

from pyhealth.models import CheckCategory, CheckResult, Issue, Severity

if TYPE_CHECKING:
    from pathlib import Path


class BaseChecker(ABC):
    """Abstract base class for all health checkers."""

    def __init__(self, project_path: Path, config: dict[str, Any] | None = None) -> None:
        self.project_path = project_path
        self.config = config or {}

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of the checker."""

    @property
    @abstractmethod
    def category(self) -> CheckCategory:
        """Category this checker belongs to."""

    @abstractmethod
    def run(self) -> CheckResult:
        """Run the check and return results."""

    def _create_result(
        self,
        passed: bool,
        score: float,
        issues: list[Issue] | None = None,
        metrics: dict[str, Any] | None = None,
    ) -> CheckResult:
        """Create a CheckResult with timing."""
        return CheckResult(
            name=self.name,
            category=self.category,
            passed=passed,
            score=score,
            issues=issues or [],
            metrics=metrics or {},
        )

    def _create_issue(
        self,
        severity: Severity,
        message: str,
        file_path: str | None = None,
        line_number: int | None = None,
        rule_id: str | None = None,
        suggestion: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Issue:
        """Create an Issue with this checker's category."""
        return Issue(
            category=self.category,
            severity=severity,
            message=message,
            file_path=file_path,
            line_number=line_number,
            rule_id=rule_id,
            suggestion=suggestion,
            metadata=metadata or {},
        )

    def _time_it(self, func: Callable[[], CheckResult]) -> CheckResult:
        """Decorator to time a function."""
        start = time.perf_counter()
        result = func()
        duration_ms = (time.perf_counter() - start) * 1000
        result.duration_ms = duration_ms
        return result


class CompositeChecker(BaseChecker):
    """A checker that runs multiple sub-checkers."""

    def __init__(
        self,
        project_path: Path,
        config: dict[str, Any] | None = None,
        checkers: list[BaseChecker] | None = None,
    ) -> None:
        super().__init__(project_path, config)
        self.checkers = checkers or []

    @property
    def name(self) -> str:
        return "Composite Checker"

    @property
    def category(self) -> CheckCategory:
        return CheckCategory.STRUCTURE

    def add_checker(self, checker: BaseChecker) -> None:
        """Add a sub-checker."""
        self.checkers.append(checker)

    def run(self) -> CheckResult:
        """Run all sub-checkers and aggregate results."""
        all_issues: list[Issue] = []
        all_metrics: dict[str, Any] = {}
        total_score = 0.0
        passed_count = 0

        for checker in self.checkers:
            result = checker.run()
            all_issues.extend(result.issues)
            all_metrics[checker.name] = result.metrics
            total_score += result.score
            if result.passed:
                passed_count += 1

        avg_score = total_score / len(self.checkers) if self.checkers else 0.0
        passed = passed_count == len(self.checkers)

        return self._create_result(
            passed=passed,
            score=avg_score,
            issues=all_issues,
            metrics={
                "sub_checks": all_metrics,
                "passed_checks": passed_count,
                "total_checks": len(self.checkers),
            },
        )
