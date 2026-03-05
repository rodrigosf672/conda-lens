#!/usr/bin/env python3
"""
Conda-Lens Environment Doctor Skill (/conda-lens)

Provides intelligent Python environment inspection, diagnostics, and fixing
for Claude Code users. Powered by the conda-lens CLI tool.
"""

import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class CondaLensSkill:
    """Main skill class for conda-lens environment diagnostics and fixing."""

    def __init__(self):
        self.conda_lens_installed = False
        self.diagnostic_results: List[Dict] = []
        self.context: Dict = {}

    # ------------------------------------------------------------------
    # Installation
    # ------------------------------------------------------------------

    def check_and_install_conda_lens(self) -> Tuple[bool, str]:
        """
        Verify conda-lens is installed; install it via pip if missing.

        Returns:
            (success, message) tuple
        """
        try:
            result = subprocess.run(
                ["conda-lens", "--help"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                self.conda_lens_installed = True
                return True, "conda-lens is already installed"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        print("conda-lens not found — installing now...")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "conda-lens"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                self.conda_lens_installed = True
                return True, "conda-lens installed successfully"
            return False, f"Installation failed: {result.stderr}"
        except Exception as exc:
            return False, f"Installation error: {exc}"

    # ------------------------------------------------------------------
    # Inspect
    # ------------------------------------------------------------------

    def run_inspect(self, env: Optional[str] = None) -> Dict:
        """
        Run `conda-lens inspect` and return structured output.

        Args:
            env: Optional conda environment name to inspect.

        Returns:
            Dictionary with 'success', 'output', 'errors', 'exit_code'.
        """
        cmd = ["conda-lens", "inspect"]
        if env:
            cmd += ["--env", env]

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30
            )
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "errors": result.stderr,
                "exit_code": result.returncode,
            }
        except Exception as exc:
            return {"success": False, "output": "", "errors": str(exc), "exit_code": -1}

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def run_diagnostics(
        self, mode: str = "full", env: Optional[str] = None, json_output: bool = False
    ) -> Dict:
        """
        Run `conda-lens diagnose` and return the raw result.

        Args:
            mode:        "full" (diagnose) or "quick" (inspect only).
            env:         Optional conda environment name.
            json_output: When True, request JSON output from the CLI.

        Returns:
            Dictionary with 'success', 'output', 'errors', 'exit_code'.
        """
        if not self.conda_lens_installed:
            return {"success": False, "output": "", "errors": "conda-lens is not installed", "exit_code": -1}

        cmd = ["conda-lens", "diagnose" if mode == "full" else "inspect"]
        if env:
            cmd += ["--env", env]
        if json_output:
            cmd.append("--json-output")

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=60
            )
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "errors": result.stderr,
                "exit_code": result.returncode,
            }
        except Exception as exc:
            return {"success": False, "output": "", "errors": str(exc), "exit_code": -1}

    def parse_diagnostic_output(self, output: str) -> Dict[str, List[str]]:
        """
        Parse plain-text conda-lens diagnostic output into severity buckets.

        Returns:
            Dictionary with 'errors', 'warnings', and 'info' lists.
        """
        issues: Dict[str, List[str]] = {"errors": [], "warnings": [], "info": []}
        current_section: Optional[str] = None

        for raw_line in output.splitlines():
            line = raw_line.strip()
            if not line or line.startswith(("╭", "╰", "─")):
                continue

            if "[ERROR]" in line:
                current_section = "errors"
                issues["errors"].append(line)
            elif "[WARNING]" in line:
                current_section = "warnings"
                issues["warnings"].append(line)
            elif "[INFO]" in line:
                current_section = "info"
                issues["info"].append(line)
            elif current_section and line:
                issues[current_section].append(line)

        return issues

    def parse_json_diagnostics(self, json_str: str) -> Dict[str, List[Dict]]:
        """
        Parse JSON diagnostic output from `conda-lens diagnose --json-output`.

        Returns:
            Dictionary with 'errors', 'warnings', 'info' bucketed by severity.
        """
        buckets: Dict[str, List[Dict]] = {"errors": [], "warnings": [], "info": []}
        try:
            items = json.loads(json_str)
            for item in items:
                severity = item.get("severity", "INFO").upper()
                if severity == "ERROR":
                    buckets["errors"].append(item)
                elif severity == "WARNING":
                    buckets["warnings"].append(item)
                else:
                    buckets["info"].append(item)
        except json.JSONDecodeError:
            pass
        return buckets

    # ------------------------------------------------------------------
    # Context gathering
    # ------------------------------------------------------------------

    def gather_context(self, directory: Optional[Path] = None) -> Dict:
        """
        Scan the working directory for project files that provide context.

        Args:
            directory: Directory to scan (defaults to cwd).

        Returns:
            Dictionary describing project context.
        """
        cwd = directory or Path.cwd()
        context: Dict = {
            "has_requirements": False,
            "has_environment_yml": False,
            "has_pyproject": False,
            "python_files": [],
            "requirements_content": None,
            "environment_yml_content": None,
            "pyproject_content": None,
        }

        for fname, key_exists, key_content in [
            ("requirements.txt", "has_requirements", "requirements_content"),
            ("environment.yml", "has_environment_yml", "environment_yml_content"),
            ("pyproject.toml", "has_pyproject", "pyproject_content"),
        ]:
            fpath = cwd / fname
            if fpath.exists():
                context[key_exists] = True
                try:
                    context[key_content] = fpath.read_text(encoding="utf-8")[:1000]
                except OSError:
                    pass

        py_files = list(cwd.glob("*.py"))[:5]
        context["python_files"] = [f.name for f in py_files]

        return context

    # ------------------------------------------------------------------
    # Conversational response generation
    # ------------------------------------------------------------------

    def generate_conversational_response(
        self, issues: Dict[str, List], context: Dict
    ) -> str:
        """
        Turn structured diagnostic issues into a human-friendly response.

        Args:
            issues:  Parsed issues from parse_diagnostic_output().
            context: Project context from gather_context().

        Returns:
            Multi-line string suitable for display to the user.
        """
        n_errors = len(issues["errors"])
        n_warnings = len(issues["warnings"])
        n_info = len(issues["info"])
        total = n_errors + n_warnings + n_info

        if total == 0:
            return (
                "Great news! Your Python environment looks healthy. "
                "All diagnostic checks passed with no issues."
            )

        parts: List[str] = []
        parts.append(
            f"I found {total} issue(s) in your Python environment "
            f"({n_errors} error(s), {n_warnings} warning(s), {n_info} info):\n"
        )

        if n_errors:
            parts.append(f"🔴 CRITICAL ISSUES ({n_errors} found):")
            for msg in issues["errors"][:3]:
                parts.append(f"  • {msg}")
            if n_errors > 3:
                parts.append(f"  … and {n_errors - 3} more")
            parts.append("")

        if n_warnings:
            parts.append(f"🟡 WARNINGS ({n_warnings} found):")
            for msg in issues["warnings"][:2]:
                parts.append(f"  • {msg}")
            if n_warnings > 2:
                parts.append(f"  … and {n_warnings - 2} more")
            parts.append("")

        if n_info:
            parts.append(f"🔵 INFO ({n_info} note(s)):")
            for msg in issues["info"][:2]:
                parts.append(f"  • {msg}")
            parts.append("")

        parts.append("RECOMMENDED ACTIONS:")

        issues_str = str(issues)
        if "Version Conflict" in issues_str or "version" in issues_str.lower():
            parts.append("  1. Resolve version conflicts:")
            parts.append("     $ conda install --update-all")
            parts.append(
                "     OR: $ pip install --upgrade <conflicting-package>"
            )

        if "Missing" in issues_str:
            parts.append("  2. Install missing dependencies:")
            if context.get("has_requirements"):
                parts.append("     $ pip install -r requirements.txt")
            else:
                parts.append("     $ pip install <missing-package>")

        if "Duplicate" in issues_str or "duplicate" in issues_str.lower():
            parts.append("  3. Remove duplicate installations:")
            parts.append(
                "     $ pip uninstall <package> && conda install <package>"
            )

        parts.append("")
        parts.append("Would you like me to:")
        parts.append("  1. Show detailed fix options for each issue")
        parts.append("  2. Automatically fix safe issues")
        parts.append("  3. Generate an environment snapshot for your team")

        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Fix suggestions
    # ------------------------------------------------------------------

    def suggest_fixes(self, issue_type: str, details: str = "") -> List[Dict]:
        """
        Return a list of fix options for a given issue type.

        Args:
            issue_type: Descriptive string (e.g. 'version_conflict').
            details:    Additional context about the specific issue.

        Returns:
            List of dicts, each with 'option', 'description', 'command',
            'pros', and 'cons'.
        """
        issue_lower = issue_type.lower()

        if "version" in issue_lower and "conflict" in issue_lower:
            return [
                {
                    "option": 1,
                    "description": "Let conda resolve all dependencies (safest)",
                    "command": "conda install -c conda-forge <packages>",
                    "pros": "Handles transitive dependencies correctly; most reliable",
                    "cons": "Slower than pip; may not have cutting-edge versions",
                },
                {
                    "option": 2,
                    "description": "Upgrade conflicting packages with pip",
                    "command": "pip install --upgrade <packages>",
                    "pros": "Fast; gets the latest versions",
                    "cons": "May introduce new conflicts if not careful",
                },
                {
                    "option": 3,
                    "description": "Pin specific versions in requirements.txt",
                    "command": "echo '<package>==<version>' >> requirements.txt && pip install -r requirements.txt",
                    "pros": "Reproducible and explicit",
                    "cons": "Requires manual maintenance over time",
                },
            ]

        if "missing" in issue_lower or "not found" in issue_lower:
            fixes = [
                {
                    "option": 1,
                    "description": "Install the missing package",
                    "command": "pip install <missing-package>",
                    "pros": "Quick and simple",
                    "cons": "May install a version incompatible with other packages",
                },
            ]
            if details and "requirements" in details.lower():
                fixes.append(
                    {
                        "option": 2,
                        "description": "Install all packages from requirements.txt",
                        "command": "pip install -r requirements.txt",
                        "pros": "Installs everything at once to a consistent state",
                        "cons": "May fail if requirements.txt has outdated pins",
                    }
                )
            return fixes

        if "duplicate" in issue_lower:
            return [
                {
                    "option": 1,
                    "description": "Remove pip copy, keep conda-managed version",
                    "command": "pip uninstall <package> && conda install <package>",
                    "pros": "Unified package management under conda",
                    "cons": "Conda may be behind on latest releases",
                },
                {
                    "option": 2,
                    "description": "Remove conda copy, keep pip-managed version",
                    "command": "conda remove <package> && pip install <package>",
                    "pros": "Faster pip updates; simpler pip-only workflow",
                    "cons": "Lose conda dependency tracking for this package",
                },
            ]

        if "cuda" in issue_lower or "gpu" in issue_lower:
            return [
                {
                    "option": 1,
                    "description": "Install a PyTorch build matching your CUDA driver",
                    "command": "pip install torch --index-url https://download.pytorch.org/whl/cu121",
                    "pros": "Official PyTorch wheel with correct CUDA build",
                    "cons": "Large download; version must match your driver",
                },
                {
                    "option": 2,
                    "description": "Use the CPU-only build if GPU is not required",
                    "command": "pip install torch --index-url https://download.pytorch.org/whl/cpu",
                    "pros": "Simpler; no CUDA dependency",
                    "cons": "No GPU acceleration",
                },
            ]

        if "abi" in issue_lower or "platform" in issue_lower or "arch" in issue_lower:
            return [
                {
                    "option": 1,
                    "description": "Reinstall the package for the correct platform",
                    "command": "pip install --force-reinstall <package>",
                    "pros": "Gets the native wheel for your architecture",
                    "cons": "Other packages that depend on it may also need reinstall",
                },
                {
                    "option": 2,
                    "description": "Use conda to install a platform-native build",
                    "command": "conda install -c conda-forge <package>",
                    "pros": "conda selects the right architecture automatically",
                    "cons": "Slower; requires conda to be set up",
                },
            ]

        # Generic fallback
        return [
            {
                "option": 1,
                "description": "Run full environment repair",
                "command": "pip check && pip install --upgrade <affected-packages>",
                "pros": "Broad fix that catches many common issues",
                "cons": "May upgrade packages you want to keep pinned",
            }
        ]

    # ------------------------------------------------------------------
    # Fix execution
    # ------------------------------------------------------------------

    def execute_fix(self, command: str) -> Tuple[bool, str]:
        """
        Execute a shell command to apply a fix.

        Always requires explicit user approval before being called.

        Args:
            command: The shell command string to execute.

        Returns:
            (success, combined stdout+stderr) tuple.
        """
        try:
            args = shlex.split(command)
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=180,
            )
            return result.returncode == 0, result.stdout + result.stderr
        except Exception as exc:
            return False, str(exc)

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def generate_snapshot(
        self, output_path: Optional[str] = None, git_commit: bool = False
    ) -> Tuple[bool, str]:
        """
        Generate an environment reproducibility snapshot.

        Args:
            output_path: File path for the snapshot (default: environment_snapshot.yaml).
            git_commit:  Whether to commit the snapshot to git.

        Returns:
            (success, message) tuple.
        """
        cmd = ["conda-lens", "snap"]
        if output_path:
            cmd += ["--output", output_path]
        if git_commit:
            cmd.append("--git")

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30
            )
            success = result.returncode == 0
            msg = result.stdout if success else result.stderr
            return success, msg.strip()
        except Exception as exc:
            return False, str(exc)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_fix(self, env: Optional[str] = None) -> Dict:
        """
        Re-run diagnostics to confirm a fix resolved the reported issues.

        Args:
            env: Optional conda environment name.

        Returns:
            Raw diagnostic result dictionary.
        """
        return self.run_diagnostics(mode="full", env=env)

    # ------------------------------------------------------------------
    # Migration planning
    # ------------------------------------------------------------------

    def plan_migration(self, target: str, dry_run: bool = True) -> Dict:
        """
        Analyse migration of all packages to a target package manager.

        Args:
            target:  One of 'pip', 'conda', 'uv', 'pixi'.
            dry_run: When True, only analyse without executing.

        Returns:
            Dictionary with 'success', 'output', 'errors'.
        """
        cmd = ["conda-lens", "switch-all", "--to", target]
        if not dry_run:
            cmd += ["--execute", "--yes"]

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=120
            )
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "errors": result.stderr,
            }
        except Exception as exc:
            return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Run a full conda-lens diagnostic session (default skill behaviour)."""
    skill = CondaLensSkill()

    # Step 1 – check / install conda-lens
    print("Checking conda-lens installation…")
    ok, msg = skill.check_and_install_conda_lens()
    print(msg)
    if not ok:
        print("ERROR: Could not install conda-lens. Aborting.")
        return

    # Step 2 – inspect
    print("\nInspecting environment…")
    inspect_result = skill.run_inspect()
    if inspect_result.get("output"):
        print(inspect_result["output"][:500])

    # Step 3 – run diagnostics
    print("\nRunning full diagnostics…")
    diag_result = skill.run_diagnostics(mode="full")
    if not diag_result.get("success") and diag_result.get("errors"):
        print(f"ERROR: {diag_result['errors']}")
        return

    # Step 4 – parse results
    issues = skill.parse_diagnostic_output(diag_result["output"])

    # Step 5 – gather context
    context = skill.gather_context()

    # Step 6 – generate conversational response
    response = skill.generate_conversational_response(issues, context)
    print("\n" + "=" * 72)
    print(response)
    print("=" * 72)


if __name__ == "__main__":
    main()
