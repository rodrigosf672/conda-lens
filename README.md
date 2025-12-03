# Conda-Lens

**The AI Environment Doctor & Reproducibility Toolkit**

Conda-Lens is a developer tool that helps data scientists and machine learning engineers inspect, diagnose, and understand their Python environments. It provides fast environment inspection, rule-based diagnostics, reproducibility cards, and a read-only migration planner that analyzes compatibility across `pip`, `conda`, `uv`, and `pixi`.

Conda-Lens includes both a command line interface and a web dashboard, giving you a clear and structured view of your environment health, package layout, and potential conflict risks.

## Features

- **Diagnose**: Detect common issues like Pip/Conda mixing, Torch/CUDA mismatches, and version conflicts.
- **Repro Card**: Generate a shareable YAML/JSON card describing your environment.
- **Lint**: Check your Python scripts for imports that are missing from your environment.
- **Migration Planner (read-only)**: Analyze migration plans between pip, conda, uv, and pixi with safety checks. No execution.
- **Inspect**: View detailed environment information including packages, Python version, and GPU details.
- **Web Dashboard**: Professional web UI for environment inspection and diagnostics.
- **Dependency-Aware Migration**: Builds package and reverse-dependency graphs to plan safe group migrations.

## Installation

```bash
pip install conda-lens
```

## Usage

### Diagnose Environment Issues

```bash
# Diagnose the current environment
conda-lens diagnose
```

### Generate Reproducibility Card

```bash
# Generate a reproducibility card
conda-lens repro-card --output environment.yaml

# Output as JSON
conda-lens repro-card --format json
```

### Lint Python Files

```bash
# Lint a single file
conda-lens lint my_script.py

# Lint entire directory
conda-lens lint src/
```

### Migration Planning (read-only)

Plan migrations between `pip`, `conda`, `uv`, and `pixi` with safety insights. The dashboard is read-only.

```bash
# Generate a migration plan (read-only)
conda-lens switch-all --to conda

# Plan for specific packages
conda-lens switch-all --to pip numpy scipy pandas

# Use specific conda channel for planning
conda-lens switch-all --to conda --channel conda-forge
```

Safety Insights:
- Version compatibility checking  
- CUDA build detection and warnings  
- Missing package detection  
- Dependency and reverse-dependency analysis  

### Inspect Environment

```bash
# View environment details
conda-lens inspect

# Output as JSON
conda-lens inspect --json-output
```

### Web Dashboard

```bash
# Start web UI at http://localhost:8000
conda-lens web

# Use custom port
conda-lens web --port 3000
```

### Other Commands

```bash
# Compare environments
conda-lens diff other-env-name

# Explain conda solver errors with LLM
conda-lens explain error.log

# Run matrix testing across Python versions
conda-lens matrix-test script.py --versions 3.10 3.11 3.12

# Download and convert HuggingFace models
conda-lens sandbox meta-llama/Llama-2-7b-hf
```

## Migration Examples

### Example 1: Migrate all pip packages to conda

```bash
conda-lens switch-all --to conda
conda-lens switch-all --to conda --execute
```

### Example 2: Migrate specific scientific packages

```bash
conda-lens switch-all --to conda numpy scipy pandas --channel conda-forge --execute
```

### Example 3: Rollback a migration

```bash
conda-lens undo
```

## Safety Model

The migration planner includes multiple safety checks:

1. Version Matching
2. CUDA Detection
3. Dependency Chain Blocking
4. Group Migration (Atomic)
5. Auto-heal rollback detection

## Web Dashboard

Start the dashboard:

```
conda-lens web --port 8000
```

Features:
- Environment summary: name, Python, path, OS/machine, conda/pip counts
- Diagnostics: rules and suggestions with clear severity
- Package search/filter: live search, manager filter
- Repro card viewer: inline preview with Copy/Download actions
- Migration planner (Switch-All): select target manager, generate plan, execute if safe
- Per-package migration: open modal, plan and execute for a single package
- Rollback: banner shows when migrations exist; undo last migration
- Dependency graphs and reverse-dependency graphs for selected package
- Blocked-package explanations and group migration preview in modal

CLI ↔ Dashboard mapping:

| Capability              | CLI                      | Dashboard                      |
|-------------------------|--------------------------|---------------------------------|
| Switch-All plan         | `conda-lens switch-all`  | Switch-All section              |
| Execute migration       | `conda-lens switch-all --execute` | Execute Migration button |
| Undo last migration     | `conda-lens undo`        | Undo Last Migration button      |
| Per-package plan        | `conda-lens switch -p`   | Package row “Switch” modal      |
| Repro card export       | `conda-lens repro-card`  | Copy/Download YAML in dashboard |

Screenshots (placeholders):
- Dashboard Overview
- Switch-All Plan
- Per-package Modal
- Rollback Banner
3. Missing Package Detection
4. Atomic Operations
5. Automatic Rollback
6. Rollback History (`~/.conda-lens/rollback.json`)

## Output Example

```
Migration Plan: → conda
Total packages to migrate: 15
...
Summary:
  Safe to migrate: 12
  Conflicts: 2
  Missing: 1
  Unsupported: 0
  Blocked: 1 (blocked by dependency chain)

Group Migration:
- Order: a → b → c
- Atomic: all-or-nothing execution with immediate rollback on failure

Auto-Heal Rollback Detection:
- After execution, environment is re-scanned; if any migrated package was replaced unexpectedly, migration is marked failed and rolled back.
```

## Contributing

Contributions are welcome! If you'd like to improve Conda-Lens, please open an issue first so we can discuss your proposed changes. After alignment, feel free to submit a Pull Request.

---

# Project Status Overview

## A. Working Features (Implemented)

### CLI Commands

- `conda-lens inspect`
  - Inspects environment via `get_active_env_info`.
  - Supports JSON output.
  - Displays environment metadata, GPU info, package subset.

- `conda-lens diagnose`
  - Runs diagnostics via `run_diagnostics`.
  - Supports JSON output.
  - Displays warnings and errors using diagnostic rules.

- `conda-lens repro-card`
  - Generates reproducibility card (YAML/JSON).
  - Uses `generate_repro_card`.

- `conda-lens lint`
  - Detects missing imports for files/directories.
  - Exits with code `1` if imports missing.

- `conda-lens explain`
  - Uses OpenAI API to explain solver errors.
  - Includes graceful error handling.

- `conda-lens matrix-test`
  - Creates temporary environments.
  - Runs provided script for multiple Python versions.
  - Outputs JSON with pass/fail per version.

- `conda-lens sandbox`
  - Downloads HuggingFace model.
  - Creates mock GGUF output (placeholder logic).

- `conda-lens switch-all`
  - Generates migration plan.
  - Supports pip/conda/uv/pixi.
  - Executes migration with rollback support.
  - Saves rollback history.

- `conda-lens undo`
  - Restores previous state from rollback file.

- `conda-lens web`
  - Launches FastAPI web dashboard.

### Dashboard Components

- Main Dashboard
  - Diagnostics panel
  - Stats grid: Python version, OS, manager counts
  - Package table with search/filter
  - Header actions (refresh, planner, repro card)

- Repro Card Viewer
  - YAML view with copy/download

- Migration Planner UI
  - Select target manager
  - Fetch `/api/migration-plan`
  - Displays detailed migration table

### API Endpoints

- `/api/refresh`
  - Returns summary of environment.

- `/api/migration-plan`
  - Returns detailed migration plan JSON.

### Internal Utilities

- Environment inspector  
- Diagnostics rule engine  
- Migration planner + resolver  
- Diff utilities  
- IPython magic  

### Tests (Passing)

- Diagnostics rules  
- Migration planner logic  
- Migration execution + rollback  
- Package resolver behavior  



## B. Partially Implemented / Missing Features

- `conda-lens diff` is not fully implemented for named env comparison.
- `TorchCudaRule` exists but disabled.
- Sandbox GGUF logic is stubbed.
- LLM explainer requires API and network.
- `web_ui_old.py` remains unused.
- `jinja2` included but unused.



## C. Known Limitations

- Manager inference is heuristic.
- GPU detection can silently fail.
- Migration `_analyze_package` lacks guard for `None` build.
- Matrix tester does not manage dependencies.
- Diff command shows instructions, not functionality.
- Subprocess error handling is broad.



## D. Architecture Summary

- CLI built with Typer + Rich.
- Web dashboard via FastAPI + Uvicorn.
- Environment inspection through Conda/Pip calls.
- Migration planner orchestrates resolver + executor + rollback.
- Unified EnvInfo model shared across CLI + dashboard.
- HTML rendered manually in Python—no Jinja2 templates.



## E. Development Roadmap (Based Only on Existing TODOs)

- Implement full `diff` against named environments.
- Re-enable and validate `TorchCudaRule`.
- Add guard for missing `pkg.build` in migration analysis.
- Replace sandbox placeholder with real GGUF conversion.
- Add backend tests for API endpoints.
- Remove unused legacy files or wire up accordingly.
Dependency-aware migration:

```
conda-lens migrate --to conda --package numpy
```

- Detects dependents that block migration.
- Validates availability of dependents and their own dependencies on target manager.
- Generates group migration order in topological sequence.
- Executes atomically with immediate rollback on failure.
## Migration Planner (Read-Only)

The dashboard now presents a read-only migration planner. It shows:

- Target manager dropdown and Analyze button
- A responsive migration plan table with safety status and reasons
- No execution controls in the UI (CLI retains full execution)

## Dependency Graph Support

- Planner builds dependency and reverse-dependency graphs
- Detects blocked packages and groups them
- Returns a `group_order` preview to aid planning

## Known Limitations → Resolved

- Infinite “Analyzing…” states resolved with robust error handling and `.finally` cleanup
- Endpoint hangs mitigated via strict 6s subprocess timeouts and structured error JSON
- UI consistently resets loading states on success and failure

## Dashboard Stability Improvements

- Endpoints log requests, subprocess commands, and exceptions
- Resolver outputs truncated to 300 chars for clean logs
- Progress bar hides automatically on completion or error

## Environment Selector Restored

- `/api/environments` returns a valid list of environments
- Selection updates the active environment and re-renders headers and tables
### Cache commands

Show cache:
```bash
conda-lens cache show
```

Cache statistics:
```bash
conda-lens cache stats
```

Clear cache:
```bash
conda-lens cache clear
```

Warm cache:
```bash
conda-lens cache warm
conda-lens cache warm --parallel
```
