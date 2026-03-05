from .base import BaseRule, DiagnosticResult
from ..env_inspect import EnvInfo
from ..version_matcher import match_version

class PythonCompatRule(BaseRule):
    @property
    def name(self) -> str:
        return "Python Version Compatibility Check"

    def check(self, env: EnvInfo) -> DiagnosticResult | None:
        """
        Checks for:
        PY-1: Package requires strictly different Python version
        PY-2: Binary build incompatibility (ABI mismatch in build string)
        """
        issues = []
        current_py = env.python_version
        
        # Heuristic for ABI tag from version: 3.10.12 -> 310
        # This is rough, as build strings vary (py310, cp310, etc.)
        if not current_py:
            return None # Can't check
            
        py_major_minor = ".".join(current_py.split(".")[:2]) # "3.10"
        abi_tag = "py" + py_major_minor.replace(".", "") # "py310"
        
        all_pkgs = [p for sublist in env.packages.values() for p in sublist]
        
        for pkg in all_pkgs:
            # PY-1: Metadata check (Requires-Python)
            if pkg.requires_python:
                if not match_version(current_py, pkg.requires_python, manager="pip"):
                    issues.append(f"{pkg.name} ({pkg.version}) requires Python {pkg.requires_python}, but current is {current_py}")
            
            # PY-2: Build string check (only for conda packages usually)
            if pkg.manager == "conda" and pkg.build:
                # Common patterns: py310_0, py39hca03da5_0, etc.
                # If build string contains "pyXY" and it doesn't match current env
                # But be careful: "py3" usually means universal? "py_0" or "pyh..."
                
                # Look for py\d+ regex
                import re
                match = re.search(r"(py\d{2,3})", pkg.build)
                if match:
                    found_tag = match.group(1)
                    # If found_tag is specific (like py39) and != abi_tag (py310)
                    # But py3 means generic python 3.
                    if found_tag.startswith("py3") and len(found_tag) > 3:
                        if found_tag != abi_tag:
                             # Wait, simple heuristic might fail.
                             # e.g. package built for py39 installed in py310 is BAD.
                             # But py310 in py310 is good.
                             # Also could be 'cp310'
                             issues.append(f"{pkg.name} ({pkg.version}) build '{pkg.build}' targets {found_tag}, likely incompatible with Python {py_major_minor}")
            
            # Check for cpXX in build
            if pkg.manager == "conda" and pkg.build:
                 match = re.search(r"(cp\d{2,3})", pkg.build)
                 if match:
                     found_tag = match.group(1)
                     expected_cp = "cp" + py_major_minor.replace(".", "")
                     if found_tag != expected_cp:
                         issues.append(f"{pkg.name} ({pkg.version}) build '{pkg.build}' targets {found_tag}, incompatible with Python {py_major_minor}")

        if issues:
            return DiagnosticResult(
                rule_name=self.name,
                severity="ERROR",
                message=f"Found {len(issues)} Python version incompatibilities:\n" + "\n".join(issues[:5]) + ("\n..." if len(issues) > 5 else ""),
                suggestion="Reinstall incompatible packages using 'conda install' to get correct builds for this Python version."
            )
        return None
