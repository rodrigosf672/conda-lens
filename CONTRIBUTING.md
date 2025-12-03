# Contributing to Conda-Lens

Thank you for your interest in contributing to Conda-Lens! This guide will help you get started with development.

## Development Setup

### 1. Clone the Repository

```bash
git clone https://github.com/rodrigosf672/conda-lens.git
cd conda-lens
```

### 2. Install in Editable Mode

```bash
# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in editable mode with dev dependencies
pip install -e ".[dev]"
```

### 3. Verify Installation

```bash
# Test CLI
conda-lens inspect

# Test web server
conda-lens web
```

## Running the Project

### CLI Development

The CLI is the primary interface. Test changes with:

```bash
# Run specific commands
conda-lens inspect
conda-lens diagnose
conda-lens repro-card

# Test migration planning
conda-lens switch-all --to conda --dry-run
```

### Backend API Development

The FastAPI backend is in `src/conda_lens/web_ui.py`:

```bash
# Start the server
conda-lens web

# Server runs at http://127.0.0.1:8000
# API docs at http://127.0.0.1:8000/docs
```

### Dashboard Development

The dashboard is embedded in `web_ui.py` as HTML/CSS/JS. To test changes:

1. Edit the HTML/JS in `web_ui.py`
2. Restart the server: `conda-lens web`
3. Refresh your browser

Note: The dashboard is intentionally kept as a single-file embedded UI for simplicity. No separate frontend build process is required.

## Code Style

### Python

We use modern Python tooling for consistency:

```bash
# Format code
black src/conda_lens

# Sort imports
isort src/conda_lens

# Lint
ruff check src/conda_lens
```

Style Guidelines:
- Use type hints where practical
- Follow PEP 8
- Keep functions focused and testable
- Add docstrings to public functions

### JavaScript

For the embedded dashboard JavaScript:

```bash
# Format (if using prettier)
prettier --write "src/conda_lens/web_ui.py"
```

Style Guidelines:
- Use modern ES6+ syntax
- Keep functions small and focused
- Use descriptive variable names
- Add comments for complex logic

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=conda_lens

# Run specific test file
pytest tests/test_diagnostics.py
```

### Writing Tests

#### Diagnostic Rule Tests

Diagnostic rules live in `src/conda_lens/rules/`. To add a new rule:

1. Create a new file in `src/conda_lens/rules/`
2. Implement the rule function
3. Add tests in `tests/test_rules/`

Example rule structure:

```python
from ..env_inspect import EnvInfo
from ..diagnostics import DiagnosticResult

def check_my_rule(env: EnvInfo) -> list[DiagnosticResult]:
    """Check for my specific condition."""
    results = []
    
    # Your logic here
    if condition:
        results.append(DiagnosticResult(
            rule_name="MyRule",
            severity="WARNING",
            message="Description of the issue",
            suggestion="How to fix it"
        ))
    
    return results
```

#### Integration Tests

Test the full CLI workflow:

```python
def test_inspect_command():
    from conda_lens.cli import app
    from typer.testing import CliRunner
    
    runner = CliRunner()
    result = runner.invoke(app, ["inspect"])
    assert result.exit_code == 0
```

## Submitting Pull Requests

### Before You Start

1. Open an issue first: Discuss your proposed changes
2. Check existing PRs: Avoid duplicate work
3. Review the roadmap: See PLAN.md for planned features

### PR Checklist

- [ ] Code follows style guidelines (black, isort, ruff)
- [ ] Tests added/updated for new functionality
- [ ] CLI commands still work (`conda-lens inspect`, `conda-lens diagnose`, etc.)
- [ ] Dashboard still works (`conda-lens web`)
- [ ] Documentation updated if needed
- [ ] No breaking changes to existing CLI commands
- [ ] Commit messages are descriptive

### PR Process

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Run tests: `pytest`
5. Format code: `black . && isort .`
6. Commit: `git commit -m "Add feature: description"`
7. Push: `git push origin feature/my-feature`
8. Open a PR with a clear description

## Architecture Notes

### Rule Engine

The diagnostic engine is rule-based:

- Location: `src/conda_lens/rules/`
- Entry Point: `src/conda_lens/diagnostics.py`
- Pattern: Each rule is a function that takes `EnvInfo` and returns `list[DiagnosticResult]`

Rules are automatically discovered and executed by `run_diagnostics()`.

### Dependency Caching Layer

Caching improves performance for repeated queries:

- In-Memory Cache: `PackageResolver._cache` (session-only)
- Disk Cache: `~/.cache/conda-lens/resolver/` (persistent)
- Cache Functions: `read_cache()`, `write_cache()` in `migration.py`

The cache stores:
- Package version lookups per manager
- Dependency graphs
- Resolver results

### Dashboard API Endpoints

All API endpoints are in `src/conda_lens/web_ui.py`:

| Endpoint | Purpose |
|----------|---------|
| `/` | Main dashboard |
| `/api/environments` | List conda environments |
| `/api/migration-plan` | Generate migration plan |
| `/api/package-plan` | Single package migration analysis |
| `/api/deps-graph` | Dependency graph data |
| `/api/compare` | Compare two environments |
| `/repro-card` | Reproducibility card viewer |
| `/migration-planner` | Dedicated migration planner page |

### Migration Planner

The migration planner (`MigrationPlanner` class) handles:

1. Analysis: Checks package availability across managers
2. Safety: Validates version compatibility
3. Dependencies: Ensures dependent packages can migrate
4. Execution: Performs actual package manager operations (CLI only)

Important: The dashboard is read-only for migrations. Execution must be done via CLI.

## Common Development Tasks

### Adding a New Diagnostic Rule

1. Create `src/conda_lens/rules/check_my_rule.py`
2. Implement the rule function
3. Add tests in `tests/test_rules/test_my_rule.py`
4. The rule will be auto-discovered

### Adding a New CLI Command

1. Add command to `src/conda_lens/cli.py`
2. Use Typer decorators: `@app.command()`
3. Add help text and examples
4. Test with `CliRunner`

### Modifying the Dashboard

1. Edit HTML/CSS/JS in `src/conda_lens/web_ui.py`
2. Use f-strings for dynamic content
3. Escape curly braces: `{{` and `}}`
4. Test by running `conda-lens web`

### Updating Cache Logic

1. Modify `PackageResolver` in `src/conda_lens/migration.py`
2. Update cache read/write functions
3. Test cache hits with logging
4. Verify cache invalidation works

## Getting Help

- Issues: Open an issue on GitHub
- Discussions: Use GitHub Discussions for questions
- Email: Contact the maintainer

## Code of Conduct

Be respectful, inclusive, and constructive. We're all here to make Conda-Lens better.

---

Thank you for contributing to Conda-Lens! 🚀
