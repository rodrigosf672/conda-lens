# Tests

## Overview
- Covers environment inspection, diagnostics rules, package migration planning/execution, and examples validation.
- Uses `pytest` with `unittest.mock` for subprocess and environment isolation.
- All tests pass on macOS with Python 3.11 (`34 passed`).

## Test Suite Structure
- `tests/test_diagnostics.py`
  - Validates `TorchCudaRule` behavior against CUDA driver and build metadata.
  - Validates `PipCondaMixRule` warning when core scientific packages are installed via `pip`.
- `tests/test_migration.py`
  - `TestPackageResolver`: mocks `subprocess.run` to test resolution across managers (`conda`, `pip`) and timeout behavior.
  - `TestMigrationPlanner`: verifies planning for all/specific packages and safety classifications: `MISSING`, `CUDA_RISK`, `CONFLICT`, `OK`.
  - `TestMigrationExecution`: dry-run behavior, successful migration path, failure triggering rollback, rollback file creation.
  - `TestMigrationReport`: summary fields and `can_proceed` logic.
- `tests/test_migration_logic.py`
  - Minimal logic tests focusing on `MigrationStep.is_safe` and `MigrationReport.can_proceed` and summary counts.
- `tests/test_examples.py`
  - Ensures `examples/notebooks` exist and each notebook contains expected `conda_lens` references.
  - Executes `examples/scripts/processing/example_pipeline.py`, parses stdout with `ast.literal_eval`, and asserts required keys in the output.
 - `tests/test_web_features.py`
   - Preferences persistence: verifies last selected environment is saved in `~/.conda-lens/prefs.json` and recalled across client instances.
   - Environment comparison: validates version mismatches and missing packages between synthetic environments via `/api/compare`.

## Running Tests
- From repository root:
  - `pytest -q`
- Run a specific file:
  - `pytest tests/test_examples.py -q`
- Show verbose output:
  - `pytest -vv`

## Environment Requirements
- Python: `>=3.11` (see `pyproject.toml`).
- Tests rely on mocking to avoid external tool invocation; no Conda/Pip operations are executed during tests.
- Example script test runs a Python process and imports local package code; it does not modify the environment.

## Mocking and Isolation
- `unittest.mock.patch('subprocess.run')` is used to:
  - Simulate `conda list/search`, `pip show/index`, and process timeouts.
  - Ensure deterministic behavior independent of host environment.
- `PackageResolver.clear_cache()` used when testing timeout paths to avoid cross-test cache pollution.

## Adding New Tests
- Prefer small, focused tests that validate one behavior per test.
- Use `EnvInfo` and `PackageDetails` to construct synthetic environments.
- When testing subprocess behavior, mock `subprocess.run` and return realistic `stdout` strings matching current implementation expectations.
- For web endpoints (e.g., `/api/refresh`, `/api/migration-plan`), consider adding FastAPI `TestClient`-based tests if needed.
  - Web features include `/api/preferences/last-env`, `/api/environments`, and `/api/compare`.

## Examples Coverage
- Notebooks checked for presence of expected tokens:
  - `data_exploration.ipynb`: `get_active_env_info`
  - `prototyping_experimentation.ipynb`: `MigrationPlanner`
  - `research_process_documentation.ipynb`: `generate_repro_card`
  - `interactive_demo.ipynb`: `conda_lens.magic`, `diagnose`
- Scripts:
  - `examples/scripts/processing/example_pipeline.py` prints environment summary; output parsed and verified.

## Maintenance Notes
- If implementation of resolver commands or output formats changes, update mocks and expected values accordingly.
- Keep tests fast: avoid real package installation/removal; rely on dry-run patterns and mocks.
- Ensure example paths remain valid if repository structure changes; update `tests/test_examples.py` accordingly.
