from typing import List
from .base import BaseRule, DiagnosticResult
from ..env_inspect import EnvInfo, PackageDetails
from ..version_matcher import match_version
import re
from packaging.requirements import Requirement

class VersionConflictRule(BaseRule):
    @property
    def name(self) -> str:
        return "Version Conflict Check"

    def check(self, env: EnvInfo) -> DiagnosticResult | None:
        """
        Checks for:
        VC-1: Direct version mismatch
        VC-2: Incompatible version ranges
        VC-3: Hard pin matches
        """
        conflicts = []
        
        # Flatten packages
        all_pkgs = [p for sublist in env.packages.values() for p in sublist]
        
        # Map name -> package (if duplicates, we might have multiple. 
        # dependencies are usually checked against ANY installed version or specific one?)
        # A dependency is satisfied if ANY installed version meets it (if multiple are co-installed, which is rare/broken).
        # We'll check if ANY installed version satisfies the requirement.
        
        for pkg in all_pkgs:
            for dep in pkg.depends:
                # Parse dependency string
                # Conda: "numpy >=1.2"
                # Pip: "numpy>=1.2"
                
                # Split name and spec
                # Heuristic: split on first space or operator
                dep_name = None
                dep_spec = None
                
                # Try PEP 508 parsing first (for pip)
                try:
                    req = Requirement(dep)
                    dep_name = req.name
                    dep_spec = str(req.specifier)
                    if not dep_spec:
                        dep_spec = "*"
                except:
                    # Fallback for conda style (simple split)
                    parts = dep.split()
                    if len(parts) >= 1:
                        dep_name = parts[0]
                        if len(parts) > 1:
                            dep_spec = " ".join(parts[1:])
                        else:
                            dep_spec = "*"
                            
                if not dep_name:
                    continue
                    
                dep_name = dep_name.lower()
                
                # Check if dependency exists
                if dep_name not in env.packages:
                    # Missing dependency (MISS-1) - handled by MissingDependencyRule
                    continue
                
                installed_list = env.packages[dep_name]
                
                # Check if ANY installed version satisfies the spec
                satisfied = False
                failed_versions = []
                
                for installed in installed_list:
                    if match_version(installed.version, dep_spec, manager=pkg.manager):
                        satisfied = True
                        break
                    else:
                        failed_versions.append(installed.version)
                
                if not satisfied:
                    conflicts.append(
                        f"{pkg.name} ({pkg.version}) requires {dep_name} {dep_spec}, but installed: {', '.join(failed_versions)}"
                    )

        if conflicts:
            return DiagnosticResult(
                rule_name=self.name,
                severity="ERROR",
                message=f"Found {len(conflicts)} version conflicts:\n" + "\n".join(conflicts[:5]) + ("\n..." if len(conflicts) > 5 else ""),
                suggestion="Try upgrading or reinstalling the conflicting packages using 'conda update' or 'pip install --upgrade'."
            )
        return None
