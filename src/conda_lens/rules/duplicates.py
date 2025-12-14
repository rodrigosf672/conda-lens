from typing import List
from .base import BaseRule, DiagnosticResult
from ..env_inspect import EnvInfo

class DuplicateRule(BaseRule):
    @property
    def name(self) -> str:
        return "Duplicate Package Check"

    def check(self, env: EnvInfo) -> DiagnosticResult | None:
        """
        Checks for:
        DUP-1: Multiple versions of same package
        DUP-2: Shadowed packages (pip vs conda duplicates)
        """
        duplicates = []
        
        for name, pkgs in env.packages.items():
            if len(pkgs) > 1:
                # We have duplicates!
                details = []
                for p in pkgs:
                    details.append(f"{p.version} ({p.manager})")
                duplicates.append(f"{name}: {', '.join(details)}")

        if duplicates:
            return DiagnosticResult(
                rule_name=self.name,
                severity="WARNING",
                message=f"Found {len(duplicates)} duplicate packages:\n" + "\n".join(duplicates[:5]) + ("\n..." if len(duplicates) > 5 else ""),
                suggestion="Remove duplicate installations using 'pip uninstall' or 'conda remove' to ensure deterministic behavior."
            )
        return None
