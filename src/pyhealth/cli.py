"""Main CLI entry point for pyhealth."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from pyhealth.checkers.ci import CICDChecker
from pyhealth.checkers.code_quality import CodeQualityChecker
from pyhealth.checkers.dependencies import DependencyChecker
from pyhealth.checkers.docs import DocumentationChecker
from pyhealth.checkers.security import SecurityChecker
from pyhealth.checkers.structure import StructureChecker
from pyhealth.checkers.tests import TestsChecker
from pyhealth.models import ProjectHealthReport
from pyhealth.report import ReportGenerator
from pyhealth.score import calculate_grade, calculate_overall_score

__version__ = "0.1.0"


@click.group()
@click.version_option(version=__version__, prog_name="pyhealth")
def main() -> None:
    """pyhealth — Python Project Health Analyzer.

    Comprehensive health scanning for Python projects:
    dependencies, code quality, security, tests, docs, and CI/CD.
    """


@main.command()
@click.argument(
    "path",
    default=".",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
)
@click.option(
    "--output",
    "-o",
    type=click.Path(dir_okay=False, writable=True),
    default=None,
    help="Output file for report (JSON, HTML, or MD based on extension).",
)
@click.option(
    "--format",
    "-f",
    type=click.Choice(["json", "html", "md", "terminal"], case_sensitive=False),
    default="terminal",
    help="Output format for the report.",
)
@click.option(
    "--fail-on",
    type=click.Choice(["any", "critical", "error", "warning"], case_sensitive=False),
    default=None,
    help="Exit with code 1 if issues of specified severity or worse are found.",
)
@click.option(
    "--min-score",
    type=float,
    default=None,
    help="Exit with code 1 if overall score is below this threshold (0-100).",
)
@click.option(
    "--skip",
    multiple=True,
    type=click.Choice(
        ["dependencies", "code-quality", "security", "tests", "docs", "ci-cd", "structure"],
        case_sensitive=False,
    ),
    help="Skip specific check categories (can be used multiple times).",
)
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    default=None,
    help="Path to configuration file (YAML/TOML).",
)
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    default=False,
    help="Suppress progress output, only show summary.",
)
def scan(
    path: str,
    output: str | None,
    format: str,
    fail_on: str | None,
    min_score: float | None,
    skip: tuple[str, ...],
    config: str | None,
    quiet: bool,
) -> None:
    """Scan a Python project for health issues."""
    console = Console(quiet=quiet)
    project_path = Path(path).resolve()

    # Load config if provided
    config_data: dict[str, Any] = {}
    if config:
        config_path = Path(config)
        if config_path.suffix in {".yaml", ".yml"}:
            import yaml

            config_data = yaml.safe_load(config_path.read_text())
        elif config_path.suffix == ".toml":
            import tomllib

            config_data = tomllib.loads(config_path.read_text())

    # Determine which checkers to run
    all_checkers = {
        "dependencies": DependencyChecker,
        "code-quality": CodeQualityChecker,
        "security": SecurityChecker,
        "tests": TestsChecker,
        "docs": DocumentationChecker,
        "ci-cd": CICDChecker,
        "structure": StructureChecker,
    }

    skip_set = set(skip)
    checkers_to_run = [
        cls(project_path, config_data) for name, cls in all_checkers.items() if name not in skip_set
    ]

    if not checkers_to_run:
        console.print("[red]Error: All checkers skipped![/red]")
        sys.exit(1)

    # Run checks
    check_results = []
    if quiet:
        for checker in checkers_to_run:
            check_results.append(checker.run())
    else:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("Running health checks...", total=len(checkers_to_run))
            for checker in checkers_to_run:
                check_results.append(checker.run())
                progress.update(task, advance=1)

    overall_score = calculate_overall_score(
        ProjectHealthReport(
            project_path=project_path,
            timestamp=datetime.now(),
            overall_score=0.0,
            grade="F",
            check_results=check_results,
        )
    )
    grade = calculate_grade(overall_score)

    report = ProjectHealthReport(
        project_path=project_path,
        timestamp=datetime.now(),
        overall_score=overall_score,
        grade=grade,
        check_results=check_results,
    )

    # Generate output
    if format == "terminal" or (format == "auto" and not output):
        _print_terminal_report(console, report, fail_on, min_score)
    elif format == "json" or (output and output.endswith(".json")):
        generator = ReportGenerator(report)
        json_str = generator.to_json(Path(output) if output else None)
        if not output:
            console.print(json_str)
    elif format == "html" or (output and output.endswith(".html")):
        generator = ReportGenerator(report)
        generator.to_html(Path(output) if output else None)
        if output:
            console.print(f"[green]HTML report saved to {output}[/green]")
    elif format == "md" or (output and output.endswith(".md")):
        generator = ReportGenerator(report)
        generator.to_markdown(Path(output) if output else None)
        if not output:
            console.print(generator.to_markdown())

    # Determine exit code
    exit_code = _determine_exit_code(report, fail_on, min_score)
    sys.exit(exit_code)


def _print_terminal_report(
    console: Console,
    report: ProjectHealthReport,
    fail_on: str | None,
    min_score: float | None,
) -> None:
    """Print report to terminal."""
    # Score card
    grade_color = _get_grade_color(report.grade)
    console.print(f"\n[bold]pyhealth Report: {report.project_path.name}[/bold]")
    console.print(f"Path: {report.project_path}")
    console.print(f"Generated: {report.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
    console.print(
        f"Overall Score: [{grade_color}]{report.overall_score:.1f}%[/{grade_color}] (Grade [bold]{report.grade}[/bold])"
    )
    console.print()

    # Check results table
    table = Table(title="Check Results", show_header=True, header_style="bold")
    table.add_column("Check", style="cyan")
    table.add_column("Category")
    table.add_column("Score", justify="right")
    table.add_column("Status", justify="center")
    table.add_column("Issues", justify="right")
    table.add_column("Duration", justify="right")

    for result in report.check_results:
        score_color = _get_score_color(result.score)
        status = "[green]✓[/green]" if result.passed else "[red]✗[/red]"
        table.add_row(
            result.name,
            result.category.value.replace("_", " ").title(),
            f"[{score_color}]{result.score:.1f}%[/{score_color}]",
            status,
            str(len(result.issues)),
            f"{result.duration_ms:.0f}ms",
        )

    console.print(table)
    console.print()

    # Issues summary
    total_issues = sum(len(r.issues) for r in report.check_results)
    if total_issues > 0:
        console.print("[bold]Issues Found:[/bold]")
        for result in report.check_results:
            if result.issues:
                console.print(f"\n[cyan]{result.name} ({result.category.value})[/cyan]")
                for issue in result.issues:
                    severity_color = _get_severity_color(issue.severity)
                    console.print(
                        f"  [{severity_color}]{issue.severity.value.upper()}[/{severity_color}] "
                        f"{issue.message}"
                        + (f" ([dim]{issue.file_path}[/dim])" if issue.file_path else "")
                        + (f" 💡 {issue.suggestion}" if issue.suggestion else "")
                    )
    else:
        console.print("[green]No issues found! 🎉[/green]")

    # Exit code info
    if fail_on or min_score is not None:
        exit_code = _determine_exit_code(report, fail_on, min_score)
        if exit_code != 0:
            console.print(f"\n[red]Exit code: {exit_code} (threshold not met)[/red]")
        else:
            console.print("\n[green]Exit code: 0 (all thresholds met)[/green]")


def _determine_exit_code(
    report: ProjectHealthReport,
    fail_on: str | None,
    min_score: float | None,
) -> int:
    """Determine exit code based on thresholds."""
    if min_score is not None and report.overall_score < min_score:
        return 1

    if fail_on:
        severity_order = {"critical": 0, "error": 1, "warning": 2, "info": 3}
        target_level = severity_order.get(fail_on.lower(), 3)

        for result in report.check_results:
            for issue in result.issues:
                if severity_order.get(issue.severity.value, 3) <= target_level:
                    return 1

    return 0


def _get_grade_color(grade: str) -> str:
    colors = {"A": "green", "B": "green", "C": "yellow", "D": "orange3", "F": "red"}
    return colors.get(grade.upper(), "white")


def _get_score_color(score: float) -> str:
    if score >= 90:
        return "green"
    if score >= 70:
        return "yellow"
    if score >= 50:
        return "orange3"
    return "red"


def _get_severity_color(severity) -> str:
    colors = {
        "critical": "red",
        "error": "red",
        "warning": "yellow",
        "info": "blue",
    }
    return colors.get(severity.value, "white")


if __name__ == "__main__":
    main()
