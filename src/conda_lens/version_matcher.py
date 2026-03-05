import re
from typing import Optional

try:
    from packaging.specifiers import SpecifierSet
    from packaging.version import Version, parse as parse_version
except ImportError:
    # Fallback or simplified logic if packaging not present?
    # It should be present in most envs, otherwise we can bundle a tiny parser
    SpecifierSet = None
    Version = None
    parse_version = None

def match_version(installed_version: str, spec: str, manager: str = "conda") -> bool:
    """
    Check if installed_version satisfies the spec.
    Handles Conda and Pip style specs.
    """
    if not spec or spec == "*":
        return True
        
    # Clean up weird chars
    spec = spec.strip()
    
    if manager == "pip" or "==" in spec or ">=" in spec or "<=" in spec or "!=" in spec or "~=" in spec:
        # PEP 440 style
        if SpecifierSet:
            try:
                # Handle semicolon markers in pip deps e.g. "numpy>=1.20; python_version<'3.10'"
                # We ignore markers here for simple version checking against the package options
                if ";" in spec:
                    spec = spec.split(";")[0].strip()
                
                # Handle 'extra' markers - usually implies dependency is optional? 
                # But here we assume we are checking a specific dependency relationship that exists.
                
                s = SpecifierSet(spec)
                return s.contains(installed_version, prereleases=True)
            except Exception:
                pass
    
    # Conda style: "numpy 1.21.*" or "numpy >=1.20"
    # Or simple space separated: "1.21.*"
    
    # Remove package name if present at start "numpy >=1.20" -> ">=1.20"
    # Actually caller usually passes just the version part or we parse it out?
    # Let's assume 'spec' is the version constraint part.
    
    # conda spec parsing is complex.
    # Simple heuristics:
    parts = spec.split()
    if len(parts) > 1:
        # ">=1.20,<2.0" is comma separated in pip, but might be space in conda?
        # conda: ">=1.2, <2.0"
        # We can try converting to PEP 440 by replacing spaces with commas
        pep_spec = spec.replace(" ", ",")
        try:
            if SpecifierSet:
                return SpecifierSet(pep_spec).contains(installed_version, prereleases=True)
        except:
            pass
            
    # Handle single comparison operator
    match = re.match(r"([<>!=]=?|~=)(.*)", spec)
    if match:
        op, ver = match.groups()
        try:
            v_inst = parse_version(installed_version)
            v_spec = parse_version(ver)
            if op == "==": return v_inst == v_spec
            if op == ">=": return v_inst >= v_spec
            if op == "<=": return v_inst <= v_spec
            if op == ">": return v_inst > v_spec
            if op == "<": return v_inst < v_spec
            if op == "!=": return v_inst != v_spec
        except:
            pass
            
    # Handle exact match "1.2.3" -> "==1.2.3"
    # But "1.2" in conda often means "1.2.*" (prefix match)
    if not any(c in spec for c in "<>!=~"):
        if installed_version == spec:
            return True
        if spec.endswith("*"):
            prefix = spec.rstrip("*")
            return installed_version.startswith(prefix)
            
    # Default fail-open or fail-close?
    # If we can't parse, assume True to avoid false positive errors? 
    # Or False?
    # Let's return True (assume compatible) if we can't parse, so we only flag explicit violations.
    return True
