from .base import BaseRule, DiagnosticResult
from ..env_inspect import EnvInfo

class LLMStackRule(BaseRule):
    @property
    def name(self) -> str:
        return "LLM Stack Compatibility"

    def check(self, env: EnvInfo) -> DiagnosticResult | None:
        # Check for LangChain + Pydantic v1/v2 issues
        # LangChain < 0.0.300 often had issues with Pydantic v2
        langchain = env.packages.get("langchain")
        pydantic = env.packages.get("pydantic")
        
        if langchain and pydantic:
            # Very rough heuristic for example purposes
            # Real check would parse versions properly
            lc_ver = langchain.version
            pyd_ver = pydantic.version
            
            if lc_ver.startswith("0.0.") and int(lc_ver.split('.')[2]) < 267 and pyd_ver.startswith("2."):
                 return DiagnosticResult(
                    rule_name=self.name,
                    severity="WARNING",
                    message=f"LangChain {lc_ver} may be incompatible with Pydantic {pyd_ver}.",
                    suggestion="Upgrade LangChain to >0.0.267 or downgrade Pydantic to <2.0."
                )

        # Check for TensorFlow + NumPy 2.0 (common upcoming issue)
        tensorflow = env.packages.get("tensorflow")
        numpy = env.packages.get("numpy")
        
        if tensorflow and numpy:
            if numpy.version.startswith("2."):
                 return DiagnosticResult(
                    rule_name=self.name,
                    severity="WARNING",
                    message=f"NumPy {numpy.version} (v2) might break TensorFlow {tensorflow.version}.",
                    suggestion="Pin numpy<2.0 until TensorFlow officially supports it."
                )
        
        return None
