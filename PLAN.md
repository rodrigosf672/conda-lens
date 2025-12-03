# Conda-Lens Roadmap

This document outlines the future direction of Conda-Lens, including planned features, stretch goals, and guiding principles.

## Guiding Principles

Conda-Lens is built on three core principles:

### 1. Fast

- Aggressive caching for resolver calls
- Minimal subprocess overhead
- Responsive dashboard with lazy loading
- Background workers for expensive operations

### 2. Transparent

- Clear diagnostic messages with actionable suggestions
- Visible cache hits and misses
- Explicit migration plans before execution
- No hidden environment mutations

### 3. Reproducible

- Deterministic environment snapshots
- Version-pinned reproducibility cards
- Shareable environment specifications
- Audit trail for migrations

Philosophy: No magic. No surprises. Just clear, fast, reproducible environment analysis.

## Roadmap

### Phase 1: Core Stability (Current)

Status: Complete

- [x] Environment inspector with multi-manager support
- [x] Rule-based diagnostic engine
- [x] Reproducibility card generation
- [x] Web dashboard with read-only migration planner
- [x] Disk-based resolver caching
- [x] Dependency graph visualization

### Phase 2: Enhanced Diagnostics (Q1 2025)

Goal: Make the diagnostic engine more powerful and actionable.

- [ ] Conflict Resolution Suggestions: Provide specific version recommendations for conflicts
- [ ] Dependency Tree Depth: Show full dependency chains, not just direct dependencies
- [ ] Cross-Manager Conflict Detection: Identify when pip and conda packages conflict
- [ ] CUDA Compatibility Matrix: Expand CUDA checks to cover more frameworks
- [ ] Python Version Compatibility: Warn about packages incompatible with current Python version
- [ ] Security Vulnerability Scanning: Integrate with vulnerability databases (optional)

### Phase 3: Reproducibility Enhancements (Q2 2025)

Goal: Expand the reproducibility card into a full "environment passport."

- [ ] Environment Passport: Rich metadata including:
  - Git repository state (if in a repo)
  - System libraries (via `ldd` or equivalent)
  - Environment variables
  - Installed system packages (apt, brew, etc.)
- [ ] Snapshot Verification: `conda-lens snapshot verify` command
- [ ] Snapshot Diff: Compare two snapshots to see what changed
- [ ] HTML Export: Generate static HTML reproducibility reports
- [ ] CI/CD Integration: GitHub Actions / GitLab CI templates

### Phase 4: Smarter Caching (Q2 2025)

Goal: Make caching more intelligent and efficient.

- [ ] Timestamped Invalidation: Auto-invalidate cache entries after N days
- [ ] Selective Cache Warming: Only warm cache for packages likely to be queried
- [ ] Cache Compression: Reduce disk usage for large environments
- [ ] Cache Sharing: Optional shared cache for teams (via network drive or S3)
- [ ] Cache Analytics: Track hit rates, stale entries, and performance gains

### Phase 5: Advanced Features (Q3 2025)

Goal: Add power-user features for complex workflows.

- [ ] Environment Diffing: `conda-lens diff env-a env-b`
  - Show added/removed/changed packages
  - Highlight version mismatches
  - Suggest migration path from A to B
- [ ] Multi-Environment Dashboard: View multiple environments side-by-side
- [ ] Export Formats:
  - Static JSON API for CI/CD
  - Markdown reports for documentation
  - CSV exports for analysis
- [ ] Dependency Graph Enhancements:
  - Interactive graph visualization
  - Circular dependency detection
  - Dependency impact analysis ("what depends on X?")

## Stretch Goals

These are ambitious features that may or may not make it into Conda-Lens, depending on community interest and maintainer bandwidth.

### 1. Expanded Migration Analysis

Vision: Support complex migration scenarios.

- Pip → UV → Conda migration paths
- Conda-forge → defaults channel migration
- Python 3.9 → 3.12 upgrade analysis
- Virtual environment → Docker container migration

### 2. Plugin System

Vision: Allow users to add custom diagnostic rules without modifying core code.

```python
# Example plugin
from conda_lens.plugin import DiagnosticPlugin

class MyCustomRule(DiagnosticPlugin):
    def check(self, env):
        # Custom logic
        return [DiagnosticResult(...)]
```

Use Cases:
- Company-specific compliance checks
- Framework-specific diagnostics (e.g., PyTorch, TensorFlow)
- Custom package manager support

### 3. AI-Powered Suggestions

Vision: Use LLM to provide intelligent suggestions for complex conflicts.

- Explain why a conflict exists in plain English
- Suggest resolution strategies based on similar environments
- Auto-generate migration scripts

Challenges:
- Requires API key (OpenAI, Anthropic, etc.)
- May not be deterministic
- Privacy concerns with environment data

### 4. Environment Templates

Vision: Save and reuse environment configurations.

```bash
# Save current environment as template
conda-lens template save ml-gpu

# Create new environment from template
conda-lens template apply ml-gpu --name new-env
```

Use Cases:
- Onboarding new team members
- Standardizing development environments
- Quick environment replication

### 5. Integration with Package Managers

Vision: Deeper integration with conda, pip, uv, and pixi.

- `conda-lens install <package>` with conflict checking
- `conda-lens upgrade <package>` with impact analysis
- `conda-lens remove <package>` with dependent package warnings

Challenges:
- Requires careful testing to avoid breaking environments
- May overlap with existing package manager features

## Non-Goals

These are explicitly not in scope for Conda-Lens:

- Full package manager replacement: Conda-Lens is an analysis tool, not a package manager
- Environment execution: We inspect environments, we don't run code in them
- Cloud-based services: Conda-Lens is a local-first tool
- GUI application: The dashboard is lightweight and web-based, not a native app
- Windows-specific features: We support Windows, but won't add Windows-only features

## How to Contribute to the Roadmap

Have an idea? Here's how to propose it:

1. Open an issue: Describe your feature request
2. Discuss: Engage with maintainers and community
3. Prototype: Build a proof-of-concept if possible
4. Submit PR: Implement the feature with tests and docs

See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## Timeline Disclaimer

This roadmap is aspirational and subject to change. Dates are estimates, not commitments. Features may be added, removed, or reprioritized based on:

- Community feedback
- Maintainer availability
- Technical feasibility
- Ecosystem changes (new package managers, Python versions, etc.)

---

Last Updated: December 2024  
Maintainer: Rodrigo Silva Ferreira
