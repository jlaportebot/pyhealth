"""Report generation for pyhealth."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from pyhealth.models import CheckCategory, ProjectHealthReport, Severity

if TYPE_CHECKING:
    from pathlib import Path


class ReportGenerator:
    """Generates health reports in various formats."""

    def __init__(self, report: ProjectHealthReport) -> None:
        self.report = report

    def to_json(self, output_path: Path | None = None) -> str:
        """Generate JSON report."""
        data = self.report.to_dict()
        json_str = json.dumps(data, indent=2, default=str)
        if output_path:
            output_path.write_text(json_str)
        return json_str

    def to_html(self, output_path: Path | None = None) -> str:
        """Generate HTML report."""
        html = self._generate_html()
        if output_path:
            output_path.write_text(html)
        return html

    def to_markdown(self, output_path: Path | None = None) -> str:
        """Generate Markdown report."""
        md = self._generate_markdown()
        if output_path:
            output_path.write_text(md)
        return md

    def _generate_html(self) -> str:
        """Generate HTML report with embedded CSS."""
        grade_color = self._get_grade_color(self.report.grade)

        # Build issues by category
        category_html = ""
        for category in [
            CheckCategory.DEPENDENCIES,
            CheckCategory.CODE_QUALITY,
            CheckCategory.SECURITY,
            CheckCategory.TESTS,
            CheckCategory.DOCUMENTATION,
            CheckCategory.CI_CD,
            CheckCategory.STRUCTURE,
        ]:
            cat_issues = self.report.get_issues_by_category(category)
            if cat_issues:
                cat_html = (
                    f'<h3>{category.value.replace("_", " ").title()}</h3>\n<ul class="issues">\n'
                )
                for issue in cat_issues:
                    severity_class = issue.severity.value
                    cat_html += f'<li class="issue {severity_class}">'
                    cat_html += f'<span class="severity-badge {severity_class}">{issue.severity.value.upper()}</span> '
                    if issue.file_path:
                        cat_html += f"<code>{issue.file_path}</code>"
                        if issue.line_number:
                            cat_html += f":{issue.line_number}"
                        cat_html += " - "
                    cat_html += issue.message
                    if issue.suggestion:
                        cat_html += f' <em class="suggestion">💡 {issue.suggestion}</em>'
                    cat_html += "</li>\n"
                cat_html += "</ul>\n"
                category_html += cat_html

        # Build check results table
        checks_html = ""
        for result in self.report.check_results:
            status_class = "passed" if result.passed else "failed"
            checks_html += f'<tr class="{status_class}">'
            checks_html += f"<td>{result.name}</td>"
            checks_html += f"<td>{result.category.value.replace('_', ' ').title()}</td>"
            checks_html += f'<td class="score">{result.score:.1f}%</td>'
            checks_html += f'<td class="{status_class}">{"✓" if result.passed else "✗"}</td>'
            checks_html += f"<td>{len(result.issues)} issues</td>"
            checks_html += f"<td>{result.duration_ms:.0f}ms</td>"
            checks_html += "</tr>\n"

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>pyhealth Report - {self.report.project_path.name}</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; color: #333; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); overflow: hidden; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; }}
        .header h1 {{ margin: 0; font-size: 2.5rem; }}
        .header .meta {{ opacity: 0.9; margin-top: 10px; }}
        .score-card {{ display: flex; justify-content: center; align-items: center; padding: 30px; background: #fafafa; border-bottom: 1px solid #eee; }}
        .score-circle {{ width: 150px; height: 150px; border-radius: 50%; display: flex; flex-direction: column; justify-content: center; align-items: center; color: white; font-weight: bold; }}
        .score-value {{ font-size: 3rem; }}
        .score-grade {{ font-size: 1.5rem; opacity: 0.9; }}
        .content {{ padding: 30px; }}
        .section {{ margin-bottom: 40px; }}
        .section h2 {{ border-bottom: 2px solid #eee; padding-bottom: 10px; margin-bottom: 20px; }}
        table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #eee; }}
        th {{ background: #fafafa; font-weight: 600; }}
        tr.passed {{ background: #f0fff4; }}
        tr.failed {{ background: #fff5f5; }}
        .score {{ font-weight: bold; }}
        .score.good {{ color: #38a169; }}
        .score.medium {{ color: #d69e2e; }}
        .score.bad {{ color: #e53e3e; }}
        .issues {{ list-style: none; padding: 0; }}
        .issues li {{ padding: 12px; margin-bottom: 8px; border-radius: 4px; background: #fafafa; border-left: 4px solid #ccc; }}
        .issues li.error {{ border-left-color: #e53e3e; background: #fff5f5; }}
        .issues li.warning {{ border-left-color: #d69e2e; background: #fffaf0; }}
        .issues li.info {{ border-left-color: #4299e1; background: #ebf8ff; }}
        .issues li.critical {{ border-left-color: #c53030; background: #fff5f5; }}
        .severity-badge {{ display: inline-block; padding: 2px 8px; border-radius: 3px; font-size: 0.75rem; font-weight: bold; text-transform: uppercase; margin-right: 8px; }}
        .severity-badge.error {{ background: #e53e3e; color: white; }}
        .severity-badge.warning {{ background: #d69e2e; color: white; }}
        .severity-badge.info {{ background: #4299e1; color: white; }}
        .severity-badge.critical {{ background: #c53030; color: white; }}
        .suggestion {{ color: #38a169; font-style: normal; }}
        code {{ background: #f0f0f0; padding: 2px 6px; border-radius: 3px; font-family: monospace; }}
        .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }}
        .summary-card {{ background: #fafafa; padding: 20px; border-radius: 8px; text-align: center; }}
        .summary-value {{ font-size: 2rem; font-weight: bold; color: #667eea; }}
        .summary-label {{ color: #666; margin-top: 5px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>pyhealth Report</h1>
            <div class="meta">
                Project: <strong>{self.report.project_path.name}</strong> |
                Path: {self.report.project_path} |
                Generated: {self.report.timestamp.strftime("%Y-%m-%d %H:%M:%S")}
            </div>
        </div>

        <div class="score-card">
            <div class="score-circle" style="background: {grade_color};">
                <div class="score-value">{self.report.overall_score:.1f}%</div>
                <div class="score-grade">Grade {self.report.grade}</div>
            </div>
        </div>

        <div class="content">
            <div class="summary">
                <div class="summary-card">
                    <div class="summary-value">{len(self.report.check_results)}</div>
                    <div class="summary-label">Checks Run</div>
                </div>
                <div class="summary-card">
                    <div class="summary-value">{sum(len(r.issues) for r in self.report.check_results)}</div>
                    <div class="summary-label">Total Issues</div>
                </div>
                <div class="summary-card">
                    <div class="summary-value">{len([r for r in self.report.check_results if r.passed])}</div>
                    <div class="summary-label">Checks Passed</div>
                </div>
                <div class="summary-card">
                    <div class="summary-value">{sum(r.duration_ms for r in self.report.check_results):.0f}ms</div>
                    <div class="summary-label">Total Duration</div>
                </div>
            </div>

            <div class="section">
                <h2>Check Results</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Check</th>
                            <th>Category</th>
                            <th>Score</th>
                            <th>Status</th>
                            <th>Issues</th>
                            <th>Duration</th>
                        </tr>
                    </thead>
                    <tbody>
                        {checks_html}
                    </tbody>
                </table>
            </div>

            <div class="section">
                <h2>Issues by Category</h2>
                {category_html or "<p>No issues found! 🎉</p>"}
            </div>
        </div>
    </div>
</body>
</html>"""

    def _generate_markdown(self) -> str:
        """Generate Markdown report."""
        lines = [
            f"# pyhealth Report: {self.report.project_path.name}",
            "",
            f"**Path:** {self.report.project_path}",
            f"**Generated:** {self.report.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Overall Score:** {self.report.overall_score:.1f}% (Grade {self.report.grade})",
            "",
            "## Check Results",
            "",
            "| Check | Category | Score | Status | Issues | Duration |",
            "|-------|----------|-------|--------|--------|----------|",
        ]

        for result in self.report.check_results:
            status = "✓" if result.passed else "✗"
            lines.append(
                f"| {result.name} | {result.category.value.replace('_', ' ').title()} | "
                f"{result.score:.1f}% | {status} | {len(result.issues)} | {result.duration_ms:.0f}ms |"
            )

        lines.append("")
        lines.append("## Issues by Category")
        lines.append("")

        for category in [
            CheckCategory.DEPENDENCIES,
            CheckCategory.CODE_QUALITY,
            CheckCategory.SECURITY,
            CheckCategory.TESTS,
            CheckCategory.DOCUMENTATION,
            CheckCategory.CI_CD,
            CheckCategory.STRUCTURE,
        ]:
            cat_issues = self.report.get_issues_by_category(category)
            if cat_issues:
                lines.append(f"### {category.value.replace('_', ' ').title()}")
                lines.append("")
                for issue in cat_issues:
                    severity_icon = {
                        Severity.CRITICAL: "🔴",
                        Severity.ERROR: "🟠",
                        Severity.WARNING: "🟡",
                        Severity.INFO: "🔵",
                    }[issue.severity]
                    lines.append(
                        f"- {severity_icon} **{issue.severity.value.upper()}**: {issue.message}"
                    )
                    if issue.file_path:
                        lines.append(
                            f"  - File: `{issue.file_path}`"
                            + (f":{issue.line_number}" if issue.line_number else "")
                        )
                    if issue.suggestion:
                        lines.append(f"  - 💡 Suggestion: {issue.suggestion}")
                    lines.append("")

        return "\n".join(lines)

    def _get_grade_color(self, grade: str) -> str:
        """Get color for grade."""
        colors = {
            "A": "#38a169",
            "B": "#48bb78",
            "C": "#d69e2e",
            "D": "#ed8936",
            "F": "#e53e3e",
        }
        return colors.get(grade.upper(), "#718096")
