# Conda-Lens 🔬

Conda-Lens is a CLI and lightweight dashboard for inspecting Python environments, diagnosing compatibility issues, analyzing dependency graphs, and generating reproducibility snapshots.

Conda-Lens helps developers understand their Python environments across `conda`, `pip`, `uv`, and `pixi` workflows. It provides fast, transparent analysis with a clean UI for viewing environment details, diagnostics, and migration planning.

![Conda-Lens Dashboard](screenshot.png)

## Demo

*Watch the full [demo here](conda-lens-demo.mov)*.

## Project Background

I come from a chemistry background and I spent years feeling confused about Python environments. Conda, pip, uv, pixi, ABI issues, missing dependencies, CUDA problems, solver errors, packages installed twice in different managers, and environments that behaved differently from one day to the next. Most tools either gave me a vague error or a wall of information that did not tell me what the actual problem was, why it happened, or what I was supposed to do. Now that I work as a QA engineer, I see the same confusion happening to beginners and to experienced developers. So I want to build something that makes this whole space clearer and easier to understand.

My intention is to implement many specific diagnostic rules, as real environments break in very specific ways. That is why the project includes checks for version conflicts, missing or wrong dependencies, duplicate installations across managers, Python ABI issues, CUDA and platform mismatches, solver problems, and the edge cases listed (see Issue #1, not fully implemented yet). The goal would be to give people explanations that are actually useful instead of leaving them to guess what went wrong.

In the future I would like to add a button that can migrate an entire environment to pip, conda, uv, or pixi. Migration planning is slow at first because resolver results need to be cached, and the bigger challenge is the message we give the user. People need clear guidance about what is safe to migrate, what will probably break, and what their options are. I want Conda-Lens to help people make informed decisions instead of forcing them to read internal solver logs.

I used AI to help write parts of the code, but I am testing and validating all the logic myself. The test suite is important because the tool is only useful if it is trustworthy. My hope is that Conda-Lens becomes something that would have helped me when I was starting out, and something that helps others avoid the same confusions.

## Features

- Environment Inspector: Deep inspection of conda, pip, and uv packages
- Diagnostic Engine: Rule-based analysis for detecting conflicts, missing dependencies, and compatibility issues
- Reproducibility Snapshots: Generate shareable environment cards with full metadata
- Dependency Graph Viewer: Visualize package dependencies and reverse dependencies
- Migration Analysis: Analyze package manager migrations (pip ↔ conda ↔ uv ↔ pixi)
- Smart Caching: Fast resolver caching for improved performance
- Web Dashboard: Optional browser-based UI for visual exploration

## Architecture

Conda-Lens consists of three layers:

1. CLI: Command-line interface for quick inspections and diagnostics
2. API: FastAPI backend providing environment data and analysis endpoints
3. Dashboard: Optional web UI for visual exploration (read-only for migrations)

## Installation

```bash
pip install conda-lens
```
**NOTE**: During development, this doesn't work. Instead, use the following:
```bash
pip install -e .
```

Requirements: Python 3.9+ recommended

## CLI Usage

[Obs.: `--env` has been implemented; add instructions here later]

### Inspect Environment

View detailed information about your current environment:

```bash
conda-lens inspect
```

Output includes environment name, path, Python version, platform info, and package list.

### Run Diagnostics

Analyze your environment for potential issues:

```bash
conda-lens diagnose
```

The diagnostic engine checks for:
- Duplicate packages across managers
- Version conflicts
- Missing dependencies
- CUDA compatibility issues
- Python version mismatches

### Diagnostics Reference (Failure Examples)

Conda-Lens implements specific rules to catch common environment breakages.

#### VC (Version Conflict)
**What it is:** A package requires a dependency version that is not satisfied by the installed version.
**Example Failure:**
```text
[ERROR] Version Conflict Check
pkg_a (1.5.0) requires numpy>=1.24, but installed: 1.21.5
Suggestion: Try upgrading or reinstalling the conflicting packages.
```

#### DUP (Duplicate Installation)
**What it is:** The same package is installed multiple times (e.g., once by conda, once by pip), causing import ambiguity.
**Example Failure:**
```text
[WARNING] Duplicate Package Check
Found duplicate packages:
numpy: 1.21.5 (conda), 1.24.3 (pip)
Suggestion: Remove duplicate installations using 'pip uninstall' or 'conda remove' to ensure deterministic behavior.
```

#### MISS (Missing Dependency)
**What it is:** A known requirement for an installed package is completely missing from the environment.
**Example Failure:**
```text
[ERROR] Missing Dependency Check
pandas (2.0.3) requires 'pytz'
Suggestion: Install missing dependencies to prevent runtime import errors.
```

#### PY (Python Compatibility)
**What it is:** A package's metadata indicates it is incompatible with the currently running Python version, or a Conda build string targets a different Python ABI (e.g., `py39` build in a Python 3.11 env).
**Example Failure:**
```text
[ERROR] Python Version Compatibility Check
scipy (1.7.3) requires Python <3.10, but current is 3.11.0
Suggestion: Reinstall incompatible packages to get correct builds.
```

#### ABI (Platform/Arch Mismatch)
**What it is:** Packages built for a different architecture (e.g., Intel `osx-64`) are installed on an ARM (`osx-arm64`) system. This often happens on Apple Silicon Macs using Rosetta types unintentionally.
**Example Failure:**
```text
[WARNING] ABI/Platform Compatibility Check
tensorflow (2.13.0) is built for 'osx-64', but environment expects 'osx-arm64'
Suggestion: Reinstall these packages to match the system architecture.
```

#### G (Graph Cycles)
**What it is:** Circular dependencies detected in the package graph.
**Example Failure:**
```text
[INFO] Dependency Graph Cycle Check
Found dependency cycle:
sphinx -> sphinx-rtd-theme -> sphinx
Suggestion: Cycles are often benign but can cause installation issues.
```

### Generate Reproducibility Snapshot

Create a reproducibility card for your environment:

```bash
# Display to stdout
conda-lens repro-card

# Save to file
conda-lens repro-card --output repro.yaml

# JSON format
conda-lens repro-card --output repro.json --format json
```

### Warm Dependency Cache

Pre-populate the resolver cache for faster analysis:

```bash
conda-lens cache warm
```

### Migration Planning

Analyze package manager migrations:

```bash
# Plan migration to conda
conda-lens switch-all --to conda

# Plan migration to pip
conda-lens switch-all --to pip

# Migrate specific packages
conda-lens switch-all --to uv numpy scipy pandas

# Execute migration (use with caution)
conda-lens switch-all --to conda --execute --yes
```

Note: Migration execution is CLI-only. The dashboard provides read-only analysis.

### Advanced Debugging

#### Matrix Testing (Smoke Tests)
Run a Python script across multiple Python versions to verify compatibility.

```bash
conda-lens matrix-test myscript.py --versions "3.10 3.11 3.12"
```

#### LLM Explanation
Use an LLM (requires API key) to explain complex conda solver error logs.

```bash
conda-lens explain solver_error.log
```

### Additional Commands

```bash
# Lint Python files for missing imports
conda-lens lint path/to/code

# Undo last migration
conda-lens undo

# Cache management
conda-lens cache refresh
conda-lens cache stats
conda-lens cache clear
```

## Dashboard Usage

Launch the web dashboard:

```bash
conda-lens web
```

The dashboard will start at `http://127.0.0.1:8000` (or next available port).

### Dashboard Features

1. Environment Selector: Switch between conda environments
2. Package Inspector: Search, filter, and view package details
3. Diagnostics Panel: Visual display of environment health
4. Reproducibility Card: View and download environment snapshots
5. Migration Planner: Analyze package manager migrations (read-only)
6. Dependency Graph: Visualize package dependencies

### Using the Migration Planner

The dashboard migration planner is read-only and provides:

- Target manager selection (pip, conda, uv, pixi)
- Safety analysis for each package
- Conflict detection
- Version availability checking
- Dependency impact analysis

Important: 
- The planner does NOT auto-trigger on page load
- Changing environments resets the target manager to "pip"
- All resolver calls use the disk cache at `~/.cache/conda-lens/resolver/`
- Migration execution must be done via CLI

### Caching for Performance

The dashboard uses aggressive caching to improve performance:

- Resolver Cache: Package version lookups are cached to disk
- Dependency Cache: Dependency graphs are cached and refreshed daily
- Cache Location: `~/.cache/conda-lens/resolver/<package>.json`

To warm the cache manually:

```bash
conda-lens cache warm
```

## Reproducibility Card

The reproducibility card captures:

- Environment metadata (name, path, Python version)
- Complete package list with versions and managers
- Platform information (OS, architecture)
- CUDA driver version (if applicable)
- GPU information (if applicable)
- Timestamp and conda-lens version

### Why It Matters

Reproducibility cards enable:

- Collaboration: Share exact environment specs with teammates
- Debugging: Reproduce issues in identical environments
- Documentation: Track environment evolution over time
- Compliance: Maintain audit trails for production environments

### Sharing Snapshots

```bash
# Generate YAML snapshot
conda-lens repro-card --output snapshot.yaml

# Generate JSON snapshot
conda-lens repro-card --output snapshot.json --format json

# Share via version control
git add snapshot.yaml
git commit -m "Add environment snapshot"
```

## Caching System

Conda-Lens uses a two-tier caching system:

### 1. In-Memory Cache

Fast lookups for the current session. Cleared when the process exits.

### 2. Disk Cache

Persistent cache stored at `~/.cache/conda-lens/resolver/`:

- Package versions: Cached per manager (conda, pip, uv, pixi)
- Dependencies: Cached dependency graphs
- TTL: Cache entries are validated on each use

### Cache Commands

```bash
# Warm the cache (pre-populate with current environment)
conda-lens cache warm

# Warm cache in parallel (faster)
conda-lens cache warm --parallel

# View cache statistics
conda-lens cache stats

# Clear all cache entries
conda-lens cache clear

# Refresh stale entries
conda-lens cache refresh
```

### Dashboard Caching Behavior

- All resolver calls check the disk cache first
- Cache hits are logged: `INFO: Using cached resolver result for <package> from <manager>`
- The dashboard automatically uses `use_disk_cache=True` for all migration planning
- Background worker refreshes dependency cache every 24 hours

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, coding standards, and how to submit pull requests.

## License

MIT License - see LICENSE file for details.
