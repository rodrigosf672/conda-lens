"""
Manager Priority Rule (SOLVE-3)

Detects conflicts when multiple package managers install the same package,
leading to unpredictable import behavior based on sys.path ordering.
"""

from typing import Optional, List, Dict
from conda_lens.rules.base import BaseRule, DiagnosticResult
from conda_lens.env_inspect import EnvInfo


class ManagerPriorityRule(BaseRule):
    """
    Detect multi-manager priority conflicts.

    This catches scenarios like:
    - pip overriding conda-installed libraries (or vice versa)
    - uv and pip disagreeing on package versions
    - pixi lock incompatible with pip-installed overrides
    - Different managers installing incompatible versions

    Scenario: SOLVE-3 from SCENARIOS.md
    """

    @property
    def name(self) -> str:
        return "manager-priority"

    def check(self, env: EnvInfo) -> Optional[DiagnosticResult]:
        conflicts: List[Dict[str, any]] = []

        # Find packages installed by multiple managers
        for name, pkg_list in env.packages.items():
            if len(pkg_list) < 2:
                continue

            # Group by manager
            by_manager = {}
            for pkg in pkg_list:
                if pkg.manager not in by_manager:
                    by_manager[pkg.manager] = []
                by_manager[pkg.manager].append(pkg)

            # If multiple managers have this package, check for conflicts
            if len(by_manager) > 1:
                managers = list(by_manager.keys())
                versions = {mgr: by_manager[mgr][0].version for mgr in managers}

                # Check if versions differ
                unique_versions = set(versions.values())
                if len(unique_versions) > 1:
                    # Different versions = definite conflict
                    severity = "high"
                    reason = "version mismatch"
                else:
                    # Same version = potential path ordering issue
                    severity = "medium"
                    reason = "path ordering ambiguity"

                conflicts.append({
                    'package': name,
                    'managers': managers,
                    'versions': versions,
                    'severity': severity,
                    'reason': reason,
                    'locations': [by_manager[mgr][0].location for mgr in managers if by_manager[mgr][0].location]
                })

        if not conflicts:
            return None

        # Separate high and medium severity
        high_severity = [c for c in conflicts if c['severity'] == 'high']
        medium_severity = [c for c in conflicts if c['severity'] == 'medium']

        message_lines = []

        if high_severity:
            message_lines.append(f"Found {len(high_severity)} high-priority conflicts (version mismatches):")
            for conflict in high_severity[:5]:
                mgr_versions = [f"{mgr}={conflict['versions'][mgr]}" for mgr in conflict['managers']]
                message_lines.append(f"{conflict['package']}: {', '.join(mgr_versions)}")

        if medium_severity:
            if high_severity:
                message_lines.append("")
            message_lines.append(f"Found {len(medium_severity)} medium-priority conflicts (path ordering):")
            for conflict in medium_severity[:3]:
                message_lines.append(
                    f"{conflict['package']} ({conflict['versions'][conflict['managers'][0]]}): "
                    f"installed by {', '.join(conflict['managers'])}"
                )

        if len(conflicts) > 8:
            message_lines.append(f"... and {len(conflicts) - 8} more")

        # Determine overall severity
        overall_severity = "ERROR" if high_severity else "WARNING"

        # Build actionable suggestion
        suggestion_parts = []
        if high_severity:
            example_pkg = high_severity[0]['package']
            preferred_manager = self._suggest_preferred_manager(high_severity[0]['managers'])
            suggestion_parts.append(
                f"Version mismatches will cause import errors. "
                f"Standardize on one manager per package. "
                f"Example for '{example_pkg}': uninstall from other managers and keep {preferred_manager} version."
            )
        else:
            suggestion_parts.append(
                "Multiple managers installing the same package can cause import ambiguity. "
                "While the versions match, sys.path ordering determines which gets imported."
            )

        suggestion_parts.append(
            "\nRecommended actions:\n"
            "1. Use 'conda list' vs 'pip list' to see which manager owns each package\n"
            "2. Uninstall duplicates: 'pip uninstall <package>' or 'conda remove --force <package>'\n"
            "3. Reinstall from preferred manager\n"
            "4. Consider using 'conda-lens switch-all --to <manager>' for batch migration"
        )

        return DiagnosticResult(
            rule_name="Multi-Manager Priority Check",
            severity=overall_severity,
            message="\n".join(message_lines),
            suggestion="".join(suggestion_parts)
        )

    def _suggest_preferred_manager(self, managers: List[str]) -> str:
        """Suggest which manager to prefer based on best practices."""
        # Preference order: conda > pip > uv > pixi
        # Rationale: conda handles compiled deps better for scientific computing
        priority_order = ['conda', 'pip', 'uv', 'pixi']

        for preferred in priority_order:
            if preferred in managers:
                return preferred

        return managers[0]  # Fallback to first
