# pyhealth — Python Project Health Analyzer

[![CI](https://github.com/jlaportebot/pyhealth/actions/workflows/ci.yml/badge.svg)](https://github.com/jlaportebot/pyhealth/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/pyhealth.svg)](https://pypi.org/project/pyhealth/)
[![Python](https://img.shields.io/pypi/pyversions/pyhealth.svg)](https://pypi.org/project/pyhealth/)
[![License](https://img.shields.io/pypi/l/pyhealth.svg)](https://github.com/jlaportebot/pyhealth/blob/main/LICENSE)

Comprehensive health scanning for Python projects: dependencies, code quality, security, tests, documentation, and CI/CD configuration.

## Features

- **Dependency Health**: Vulnerability scanning (via pip-audit), outdated package detection, license compliance
- **Code Quality**: Linting (ruff), formatting (ruff format), type checking (ty)
- **Security**: Static analysis (bandit), secrets detection, security configuration checks
- **Tests**: Coverage measurement, test configuration validation
- **Documentation**: README completeness, docstring coverage, type hint coverage, CHANGELOG
- **CI/CD**: GitHub Actions workflow validation, pre-commit configuration
- **Project Structure**: src/ layout, essential files, Python version specification

## Installation

```bash
pip install pyhealth
# or
uv add pyhealth
```

## Usage

```bash
# Scan current directory
pyhealth scan

# Scan specific path
pyhealth scan /path/to/project

# Output as JSON
pyhealth scan --format json --output report.json

# Output as HTML
pyhealth scan --format html --output report.html

# Output as Markdown
pyhealth scan --format md --output report.md

# Fail on critical issues
pyhealth scan --fail-on critical

# Fail if score below threshold
pyhealth scan --min-score 70

# Skip specific checkers
pyhealth scan --skip security --skip docs

# Quiet mode (summary only)
pyhealth scan --quiet
```

## Configuration

Create a `pyhealth.yaml` or `pyhealth.toml` configuration file:

```yaml
# pyhealth.yaml
fail_on: "warning"
min_score: 70
skip:
  - security
  - docs
```

Or in `pyproject.toml`:

```toml
[tool.pyhealth]
fail_on = "warning"
min_score = 70
skip = ["security", "docs"]
```

## Output Formats

### Terminal (default)
Rich formatted table with color-coded scores and issues.

### JSON
Machine-readable output for CI/CD integration.

### HTML
Standalone HTML report with interactive issue browsing.

### Markdown
GitHub-flavored markdown for documentation.

## Exit Codes

- `0`: All checks passed, thresholds met
- `1`: Issues found exceeding thresholds

## Checks Performed

| Category | Checks |
|----------|--------|
| Dependencies | pip-audit vulnerabilities, outdated packages, license file |
| Code Quality | ruff lint, ruff format, ty type check |
| Security | bandit static analysis, secrets detection, .gitignore, SECURITY.md |
| Tests | pytest with coverage, pytest configuration |
| Documentation | README sections, docstring coverage, type hints, examples, CHANGELOG |
| CI/CD | GitHub Actions workflows, pre-commit config |
| Structure | src/ layout, essential files, Python version, virtual environment |

## Development

```bash
# Install dev dependencies
uv sync --all-groups

# Run tests
uv run pytest

# Lint
uv run ruff check .
uv run ruff format --check .

# Type check
uv run ty check src/
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please read our [contributing guidelines](CONTRIBUTING.md) first.

## Security

Please report security vulnerabilities to our [security policy](SECURITY.md).