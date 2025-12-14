from .base import BaseRule, DiagnosticResult
from ..env_inspect import EnvInfo

class LLMStackRule(BaseRule):
    @property
    def name(self) -> str:
        return "LLM Stack Compatibility"

    def check(self, env: EnvInfo) -> DiagnosticResult | None:
        """
        Checks for known incompatibilities in LLM/Data stacks.
        """
        # Check for LangChain + Pydantic v1/v2 issues
        # LangChain < 0.0.300 often had issues with Pydantic v2
        langchain_list = env.packages.get("langchain", [])
        pydantic_list = env.packages.get("pydantic", [])
        
        # Check combinations
        for langchain in langchain_list:
            for pydantic in pydantic_list:
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
        tensorflow_list = env.packages.get("tensorflow", [])
        numpy_list = env.packages.get("numpy", [])
        
        for tensorflow in tensorflow_list:
            for numpy in numpy_list:
                # TF < 2.16 usually needs numpy < 2
                # But let's just flag NumPy 2.x with TF < 2.16
                if numpy.version.startswith("2."):
                    # Check TF version parsing properly
                    if tensorflow.version.startswith("2."):
                        try:
                            minor = int(tensorflow.version.split('.')[1])
                            if minor < 16:
                                return DiagnosticResult(
                                    rule_name=self.name,
                                    severity="ERROR",
                                    message=f"TensorFlow {tensorflow.version} is likely incompatible with NumPy {numpy.version}.",
                                    suggestion="Upgrade TensorFlow to >=2.16 or downgrade NumPy to <2.0."
                                )
                        except:
                            pass
        
        return None
