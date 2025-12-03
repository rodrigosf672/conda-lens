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
                pkg = env.packages[pkg_name]
                if pkg.manager == "pip":
                    mixed_pkgs.append(pkg_name)
        
        if mixed_pkgs:
            return DiagnosticResult(
                rule_name=self.name,
                severity="WARNING",
                message=f"Found core scientific packages installed via pip: {', '.join(mixed_pkgs)}.",
                suggestion="Consider installing these via conda to ensure binary compatibility with system libraries (BLAS, LAPACK, etc.)."
            )
        return None
