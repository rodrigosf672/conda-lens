from .base import BaseRule, DiagnosticResult
from ..env_inspect import EnvInfo
import os

class EdgeRules(BaseRule):
    @property
    def name(self) -> str:
        return "Edge Case / System State Check"

    def check(self, env: EnvInfo) -> DiagnosticResult | None:
        """
        Checks for:
        EDGE-1: Packages installed in user site-packages (~/.local) visible to the environment.
        """
        issues = []
        all_pkgs = [p for sublist in env.packages.values() for p in sublist]
        
        # Check for .local or AppData/Roaming/Python site-packages
        # Heuristic: if location contains ".local" (Linux/Mac) or "AppData" (Windows)
        # AND it's NOT inside the env path.
        
        env_path_str = str(env.path)
        
        for pkg in all_pkgs:
            if pkg.location:
                loc = pkg.location
                if ".local/lib/python" in loc or "AppData" in loc:
                    # Check if it really is outside env
                     if env_path_str not in loc:
                        issues.append(f"{pkg.name} ({pkg.version}) found in user site-packages: {loc}")
        
        if issues:
            return DiagnosticResult(
                rule_name="User Site-Packages Leakage",
                severity="WARNING",
                message=f"Found {len(issues)} packages from user site-packages leaking into environment:\n" + "\n".join(issues[:5]),
                suggestion="This can cause hard-to-debug version conflicts. Consider disabling user site-packages by setting 'export PYTHONNOUSERSITE=1'."
            )
        return None
