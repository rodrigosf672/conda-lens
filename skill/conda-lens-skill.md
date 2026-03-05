# Conda-Lens Environment Doctor (/conda-lens)

**Powered by conda-lens** - Intelligent Python environment diagnostics, dependency analysis, and reproducibility toolkit.

## Description

The `/conda-lens` skill helps developers inspect, diagnose, and fix Python environment issues using conda-lens. It detects version conflicts, missing dependencies, duplicate installations, CUDA mismatches, ABI problems, and multi-manager conflicts, then explains findings in plain English and suggests actionable fixes.

## Trigger

User types `/conda-lens` or describes Python environment problems such as:
- "ImportError: No module named X"
- "Version conflict detected"
- "My code works locally but fails in CI"
- "CUDA version mismatch"
- "My environment is broken after updating packages"
- "Can you snapshot my environment?"

## What This Skill Does

1. **Auto-installs conda-lens** if not present
2. **Inspects the active environment** (packages, Python version, platform, CUDA)
3. **Runs full diagnostics** (13 rules covering 60+ real-world scenarios)
4. **Explains issues** in plain English with context-aware suggestions
5. **Proposes multiple fix options** with pros/cons for each
6. **Executes fixes** only after explicit user approval
7. **Validates** that the fix resolved the problem
8. **Generates environment snapshots** for sharing with teammates or CI

## Skill Behavior

### Step 1: Check / Install conda-lens
```bash
# Verify conda-lens is available
which conda-lens || pip install conda-lens
```

### Step 2: Inspect the Environment
```bash
conda-lens inspect
```

### Step 3: Run Diagnostics
```bash
# Full diagnostic pass (13 rules)
conda-lens diagnose

# JSON output for programmatic parsing
conda-lens diagnose --json-output
```

### Step 4: Parse and Categorize Results

Look for lines tagged with severity levels:
- **[ERROR]** – critical issues (version conflicts, missing dependencies, Python incompatibility)
- **[WARNING]** – potential problems (duplicates, ABI mismatches, editable-install shadows)
- **[INFO]** – advisory notes (dependency cycles, multi-manager usage)

### Step 5: Gather Context

Scan the current directory for:
- `requirements.txt` or `environment.yml` — pinned dependency specs
- `pyproject.toml` — build system requirements
- `*.py` files — import statements that may reveal missing packages
- Recent error messages in the conversation — stack traces, import errors, solver logs

### Step 6: Conversational Response

Transform raw diagnostic output into friendly, actionable explanations.

**Raw output example:**
```
[ERROR] Version Conflict Check
traitlets (5.14.3) requires pytest <8.2,>=7.0, but installed: 9.0.2
```

**Conversational response example:**
```
I found a problem in your environment!

Your Jupyter stack has a version conflict:
- traitlets 5.14.3 needs pytest >=7.0,<8.2
- But pytest 9.0.2 is currently installed

This often happens when conda and pip both manage overlapping packages.

Fix options:

Option 1 – Let conda manage everything (safest, ~2 min):
  $ conda install -c conda-forge traitlets ipython pytest
  Pros: Resolves all dependencies correctly
  Cons: Slower; conda may not have the absolute latest versions

Option 2 – Downgrade pytest with pip (quick, ~10 sec):
  $ pip install 'pytest<8.2'
  Pros: Fast, targeted fix
  Cons: Temporary; another update may re-introduce the conflict

Option 3 – Upgrade traitlets (modern, ~30 sec):
  $ pip install --upgrade traitlets
  Pros: Gets newer code that may already support pytest 9
  Cons: May break Jupyter extensions relying on older traitlets API

Which option would you like me to try?
```

### Step 7: Execute Fix (with approval)
```python
# Present chosen command to user
# Wait for explicit confirmation (yes/no)
# Run command and capture output
# Re-run conda-lens diagnose to confirm fix
```

### Step 8: Validate
```bash
conda-lens diagnose  # Re-run to confirm the issue is resolved
```

## Command Modes

### Basic Usage
| Command | Description |
|---------|-------------|
| `/conda-lens` | Full inspection + diagnostics with explanations |
| `/conda-lens --quick` | 5-second health check (inspect only) |
| `/conda-lens --fix` | Diagnose and interactively apply fixes |
| `/conda-lens --json` | Output raw JSON for scripting |

### Specific Diagnostic Focus
| Command | Description |
|---------|-------------|
| `/conda-lens conflicts` | Show version conflicts only |
| `/conda-lens duplicates` | Show packages installed by multiple managers |
| `/conda-lens missing` | Show missing or broken dependencies |
| `/conda-lens cuda` | CUDA/GPU compatibility check |
| `/conda-lens abi` | Platform/architecture mismatch check |
| `/conda-lens python` | Python version compatibility issues |

### Environment Snapshots & Collaboration
| Command | Description |
|---------|-------------|
| `/conda-lens snapshot` | Generate a shareable YAML snapshot |
| `/conda-lens snapshot --git` | Snapshot and commit to git |
| `/conda-lens ci-check` | Validate environment for CI/CD deployment |

### Migration Planning
| Command | Description |
|---------|-------------|
| `/conda-lens migrate pip` | Plan migration of all packages to pip |
| `/conda-lens migrate conda` | Plan migration of all packages to conda |
| `/conda-lens migrate uv` | Plan migration of all packages to uv |

### Advanced
| Command | Description |
|---------|-------------|
| `/conda-lens matrix myscript.py` | Run script across multiple Python versions |
| `/conda-lens explain error.log` | Use LLM to explain a conda solver error log |
| `/conda-lens web` | Launch the interactive web dashboard |
| `/conda-lens undo` | Undo the last migration |

## What It Detects (13 Diagnostic Rules)

| Rule | Code | Description |
|------|------|-------------|
| Version Conflict | VC | Package A requires version X of dep, but version Y is installed |
| Duplicate Installation | DUP | Same package installed by pip AND conda (import ambiguity) |
| Missing Dependency | MISS | A required package is not installed at all |
| Python Incompatibility | PY | Package doesn't support the current Python version |
| ABI / Platform Mismatch | ABI | Binary built for wrong architecture (e.g., x86 on ARM) |
| Dependency Cycle | G | Circular dependency detected in the package graph |
| Editable Install Shadow | EDI | `pip install -e` masking an installed package |
| Corrupt Metadata | CORRUPT | Missing or malformed package dist-info |
| Multi-Manager Conflict | MGR | pip, conda, uv, and/or pixi all managing the same package |
| CUDA / GPU Mismatch | CUDA | PyTorch/TensorFlow CUDA version doesn't match driver |
| ML Framework Conflict | ML | Conflicting versions of PyTorch, TensorFlow, or JAX |
| Manager Priority Issue | PRI | Packages installed in wrong manager order |
| Generic / Advanced | GEN | Other detected environment anomalies |

## Example Workflows

### Workflow 1: Import Error
```
User: "ImportError: No module named pandas"

Claude runs: /conda-lens

Output:
"Found it! pandas is listed in requirements.txt but not installed.

Fix:
  $ pip install pandas

Should I run that?"

User: "yes"

Claude installs pandas.
"✅ Fixed! pandas 2.2.0 installed. Try running your code again."
```

### Workflow 2: CI vs Local Mismatch
```
User: "Tests pass locally but fail on GitHub Actions"

Claude runs: /conda-lens ci-check

Output:
"Environment mismatch detected!

Local:  Python 3.11, numpy 1.26.4
CI:     Python 3.9,  numpy 1.21.6

Your code uses numpy.exceptions (added in 1.24).

Options:
1. Upgrade CI to Python 3.11 (recommended) — update .github/workflows
2. Pin numpy>=1.24 in requirements.txt
3. Add a compatibility shim in your code

I recommend Option 1. Want me to update the workflow file?"
```

### Workflow 3: Environment Snapshot for Teammates
```
User: "Can you snapshot my environment so I can share it with my team?"

Claude runs: /conda-lens snapshot

Output:
"✅ Snapshot saved to environment_snapshot.yaml

It includes:
- Python 3.11.8
- 42 packages (conda + pip)
- Platform: linux-64
- CUDA Driver: 12.1

Share this file with your team or commit it with:
  git add environment_snapshot.yaml && git commit -m 'Add env snapshot'"
```

### Workflow 4: Migration Planning
```
User: "I want to move everything from conda to pip"

Claude runs: /conda-lens migrate pip

Output:
"Migration analysis for → pip:

Safe to migrate (35 packages): numpy, pandas, scikit-learn, ...
Needs attention (4 packages):
  - cudatoolkit: no pip equivalent, keep in conda
  - mkl: binary package, conda recommended
  - ...

Estimated risk: LOW

Want me to generate the migration commands?"
```

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  User Types: /conda-lens                            │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────┐
│  Claude Code Skill (conda_lens_skill.py)            │
│  1. Check / install conda-lens                      │
│  2. Run inspect + diagnose (13 rules)               │
│  3. Parse structured results                        │
│  4. Gather context (requirements, imports, logs)    │
│  5. Generate conversational response                │
│  6. Suggest fixes with pros/cons                    │
│  7. Execute fix (with permission)                   │
│  8. Validate fix worked                             │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────┐
│  conda-lens CLI (backend engine)                    │
│  - 13 diagnostic rules                              │
│  - 60+ real-world scenario coverage                 │
│  - Multi-manager support (pip/conda/uv/pixi)        │
│  - Smart disk caching                               │
│  - Reproducibility snapshots                        │
│  - Web dashboard (optional)                         │
└─────────────────────────────────────────────────────┘
```

## Installation for Claude Code Users

1. **Install conda-lens** (one-time):
   ```bash
   pip install conda-lens
   ```

2. **Add the skill to Claude Code**:
   - Copy `conda-lens-skill.md` to your Claude Code skills directory
   - Copy `conda_lens_skill.py` to the same location

3. **Use it**:
   ```
   /conda-lens
   ```

The skill will auto-install conda-lens if it is not already present.

## Requirements

- Python 3.9+
- conda-lens (auto-installed by the skill if missing)
- Optional: conda, uv, or pixi if managing packages with those tools
- Optional: NVIDIA drivers + `nvidia-ml-py` for CUDA diagnostics
