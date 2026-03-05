"""
Editable Install Shadow Rule (EDGE-1)

Detects when pip editable installs (-e) shadow regular installations,
causing import ambiguity and unpredictable behavior.
"""

from typing import Optional
from conda_lens.rules.base import BaseRule, DiagnosticResult
from conda_lens.env_inspect import EnvInfo


class EditableInstallShadowRule(BaseRule):
    """
    Detect editable installs shadowing regular package installations.

    This catches scenarios like:
    - pip install -e . + pip install package (same package)
    - Local directory in sys.path overriding site-packages
    - uv adding path entries while pip has the package installed

    Scenario: EDGE-1 from SCENARIOS.md
    """

    @property
    def name(self) -> str:
        return "editable-shadow"

    def check(self, env: EnvInfo) -> Optional[DiagnosticResult]:
        editable_packages = []
        shadowed_packages = []

        for name, pkg_list in env.packages.items():
            if len(pkg_list) < 2:
                continue

            # Check if any package is editable (location contains .egg-link or has editable metadata)
            has_editable = False
            has_regular = False

            for pkg in pkg_list:
                # Editable installs typically have location pointing to source directory
                # or contain development paths like /Users/..., /home/..., not site-packages
                if pkg.location:
                    is_editable = (
                        '.egg-link' in pkg.location or
                        '-e ' in pkg.location or
                        ('site-packages' not in pkg.location and
                         ('Users' in pkg.location or 'home' in pkg.location or 'dev' in pkg.location))
                    )

                    if is_editable:
                        has_editable = True
                        editable_packages.append((name, pkg.version, pkg.location))
                    else:
                        has_regular = True

            # If we have both editable and regular, it's a shadow situation
            if has_editable and has_regular:
                shadowed_packages.append(name)

        if not shadowed_packages:
            return None

        message_lines = [f"Found {len(shadowed_packages)} package(s) with editable install shadowing:"]
        for name in shadowed_packages[:5]:  # Show first 5
            pkg_details = []
            for pkg in env.packages[name]:
                loc_type = "editable" if pkg.location and 'site-packages' not in pkg.location else "regular"
                pkg_details.append(f"{pkg.version} ({loc_type})")
            message_lines.append(f"{name}: {', '.join(pkg_details)}")

        if len(shadowed_packages) > 5:
            message_lines.append(f"... and {len(shadowed_packages) - 5} more")

        return DiagnosticResult(
            rule_name="Editable Install Shadow Check",
            severity="WARNING",
            message="\n".join(message_lines),
            suggestion=(
                "Editable installs can cause import ambiguity. "
                "Use 'pip list -v' to see installation paths. "
                "Consider removing the editable install if not actively developing: "
                "'pip uninstall <package>' then 'pip install <package>'"
            )
        )
