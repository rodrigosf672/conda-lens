from typing import List
from .base import BaseRule, DiagnosticResult
from ..env_inspect import EnvInfo
from packaging.requirements import Requirement

class MissingDependencyRule(BaseRule):
    @property
    def name(self) -> str:
        return "Missing Dependency Check"

    def check(self, env: EnvInfo) -> DiagnosticResult | None:
        """
        Checks for:
        MISS-1: Dependencies required by installed packages but currently missing.
        """
        missing = []
        all_pkgs = [p for sublist in env.packages.values() for p in sublist]
        
        for pkg in all_pkgs:
            for dep in pkg.depends:
                dep_name = None
                try:
                    req = Requirement(dep)
                    dep_name = req.name
                except:
                    parts = dep.split()
                    if len(parts) >= 1:
                        dep_name = parts[0]
                
                if not dep_name:
                    continue
                    
                # Conda dependency names are lower case usually
                # Pip dependency names are case insensitive
                dep_key = dep_name.lower()
                
                # Check if present in env
                # NOTE: Some packages have "extra" requirements or markers that we might fail to parse properly without full environment markers context.
                # e.g. "importlib-metadata; python_version < '3.8'"
                # If we are on 3.10, this dependency is NOT missing, it's irrelevant.
                # My simple parser in VersionMatches/here might default to thinking it's required.
                
                # Simple heuristic for markers: if ';' in dep, skip checking for missing to avoid false positives.
                if ";" in dep:
                    continue
                    
                if dep_key not in env.packages:
                    # Also check for "python" which is not a package in env.packages usually, but a specialized key?
                    # valid env.packages includes 'python' usually.
                    if dep_key == "python":
                        continue 
                        
                    missing.append(f"{pkg.name} ({pkg.version}) requires '{dep_name}'")

        if missing:
            return DiagnosticResult(
                rule_name=self.name,
                severity="ERROR",
                message=f"Found {len(missing)} missing dependencies:\n" + "\n".join(missing[:5]) + ("\n..." if len(missing) > 5 else ""),
                suggestion="Install missing dependencies to prevent runtime import errors."
            )
        return None
