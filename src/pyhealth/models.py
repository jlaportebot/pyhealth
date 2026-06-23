"""Data models for pyhealth."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import datetime
    from pathlib import Path


class Severity(Enum):
    """Issue severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class CheckCategory(Enum):
    """Categories of health checks."""

    DEPENDENCIES = "dependencies"
    CODE_QUALITY = "code_quality"
    SECURITY = "security"
    TESTS = "tests"
    DOCUMENTATION = "documentation"
    CI_CD = "ci_cd"
    STRUCTURE = "structure"


@dataclass
class Issue:
    """A single health issue found during analysis."""

    category: CheckCategory
    severity: Severity
    message: str
    file_path: str | None = None
    line_number: int | None = None
    rule_id: str | None = None
    suggestion: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "category": self.category.value,
            "severity": self.severity.value,
            "message": self.message,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "rule_id": self.rule_id,
            "suggestion": self.suggestion,
            "metadata": self.metadata,
        }


@dataclass
class CheckResult:
    """Result of a single health check."""

    name: str
    category: CheckCategory
    passed: bool
    score: float  # 0.0 to 100.0
    issues: list[Issue] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "category": self.category.value,
            "passed": self.passed,
            "score": self.score,
            "issues": [i.to_dict() for i in self.issues],
            "metrics": self.metrics,
            "duration_ms": self.duration_ms,
        }


@dataclass
class ProjectHealthReport:
    """Complete health report for a project."""

    project_path: Path
    timestamp: datetime
    overall_score: float
    grade: str
    check_results: list[CheckResult]
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "project_path": str(self.project_path),
            "timestamp": self.timestamp.isoformat(),
            "overall_score": self.overall_score,
            "grade": self.grade,
            "check_results": [r.to_dict() for r in self.check_results],
            "summary": self.summary,
        }

    def get_issues_by_severity(self, severity: Severity) -> list[Issue]:
        """Get all issues of a specific severity."""
        issues = []
        for result in self.check_results:
            issues.extend([i for i in result.issues if i.severity == severity])
        return issues

    def get_issues_by_category(self, category: CheckCategory) -> list[Issue]:
        """Get all issues of a specific category."""
        issues = []
        for result in self.check_results:
            if result.category == category:
                issues.extend(result.issues)
        return issues
