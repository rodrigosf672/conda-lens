from .base import BaseRule, DiagnosticResult
from ..env_inspect import EnvInfo

class PipCondaMixRule(BaseRule):
    @property
    def name(self) -> str:
        return "Pip/Conda Mix Check"

    def check(self, env: EnvInfo) -> DiagnosticResult | None:
        # Critical scientific packages that should ideally be from conda in a conda env
        critical_packages = ["numpy", "pandas", "scipy", "scikit-learn"]
        
        mixed_pkgs = []
        for pkg_name in critical_packages:
            if pkg_name in env.packages:
                pkgs = env.packages[pkg_name]
                # Check if ANY of the installed versions are pip managed
                # If we have [conda, pip] (same version), we might flag it if our rule logic says so.
                # The rule checks for "core scientific packages ... installed via pip".
                # If we have a conda version, that's good. If we ONLY have pip, that's bad.
                # If we have both, it's ambiguous but arguably okay if conda is primary?
                # Let's say: if NO conda version exists, but a pip version exists.
                
                has_conda = any(p.manager == "conda" for p in pkgs)
                has_pip = any(p.manager == "pip" for p in pkgs)
                
                if has_pip and not has_conda:
                    mixed_pkgs.append(pkg_name)
        
        if mixed_pkgs:
            return DiagnosticResult(
                rule_name=self.name,
                severity="WARNING",
                message=f"Found core scientific packages installed via pip: {', '.join(mixed_pkgs)}.",
                suggestion="Consider installing these via conda to ensure binary compatibility with system libraries (BLAS, LAPACK, etc.)."
            )
        return None
