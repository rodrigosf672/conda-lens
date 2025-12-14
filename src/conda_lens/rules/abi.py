from .base import BaseRule, DiagnosticResult
from ..env_inspect import EnvInfo
import platform

class ABIRule(BaseRule):
    @property
    def name(self) -> str:
        return "ABI/Platform Compatibility Check"

    def check(self, env: EnvInfo) -> DiagnosticResult | None:
        """
        Checks for:
        ABI-1: Packages installed for wrong architecture (e.g. osx-64 on arm64).
        """
        issues = []
        
        # Determine expected platform
        # env.platform_machine usually 'arm64' or 'x86_64'
        # env.os_info 'Darwin-...' or 'Linux-...'
        
        expected_subdir = None
        if "Darwin" in env.os_info:
            if env.platform_machine == "arm64":
                expected_subdir = "osx-arm64"
                # But Rosetta 2 allows osx-64. 
                # Diagnostic: Warning if mixed? Or Error if mostly arm64 but one osx-64?
                # If python is arm64, extension modules MUST be arm64.
                # If python is x86_64 (under Rosetta), then packages MUST be osx-64.
            else:
                expected_subdir = "osx-64"
        elif "Linux" in env.os_info:
            if env.platform_machine == "aarch64":
                expected_subdir = "linux-aarch64"
            else:
                expected_subdir = "linux-64"
        elif "Windows" in env.os_info:
             if env.platform_machine == "AMD64" or "64" in env.platform_machine:
                 expected_subdir = "win-64"
             else:
                 expected_subdir = "win-32"

        # Check Python binary architecture to be sure (EnvInfo doesn't expose it explicitly but machine probably reflects it?)
        # Actually `env.platform_machine` comes from `platform.machine()`, which reports the *kernel* or *process* arch.
        # on M1, native python -> arm64. Rosetta python -> x86_64.
        
        if not expected_subdir:
            return None # Unknown platform

        # Allow noarch
        valid_subdirs = {expected_subdir, "noarch"}

        all_pkgs = [p for sublist in env.packages.values() for p in sublist]
        
        for pkg in all_pkgs:
            if pkg.manager == "conda" and pkg.subdir:
                if pkg.subdir not in valid_subdirs:
                    # On M1, finding osx-64 packages in an osx-arm64 env is a PROBLEM for binary compatibility.
                    issues.append(f"{pkg.name} ({pkg.version}) is built for '{pkg.subdir}', but environment expects '{expected_subdir}'")
        
        if issues:
            return DiagnosticResult(
                rule_name=self.name,
                severity="WARNING", # Warning because it might run (Rosetta), but it's risky/slow.
                message=f"Found {len(issues)} platform ABI mismatches:\n" + "\n".join(issues[:5]) + ("\n..." if len(issues) > 5 else ""),
                suggestion="Reinstall these packages to match the system architecture."
            )
        return None
