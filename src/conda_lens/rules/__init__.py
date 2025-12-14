from .base import BaseRule, DiagnosticResult
from .generic import PipCondaMixRule
from .torch_cuda import TorchCudaRule
from .llm_stack import LLMStackRule
from .version_conflicts import VersionConflictRule
from .duplicates import DuplicateRule
from .missing_deps import MissingDependencyRule
from .python_compat import PythonCompatRule
from .abi import ABIRule
from .graph import GraphRule
from .advanced import EdgeRules

ALL_RULES = [
    PipCondaMixRule,
    TorchCudaRule,
    LLMStackRule,
    VersionConflictRule,
    DuplicateRule,
    MissingDependencyRule,
    PythonCompatRule,
    ABIRule,
    GraphRule,
    EdgeRules
]
