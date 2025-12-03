from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from ..env_inspect import EnvInfo

@dataclass
class DiagnosticResult:
    rule_name: str
    severity: str  # "INFO", "WARNING", "ERROR"
    message: str
    suggestion: Optional[str] = None

class BaseRule(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def check(self, env: EnvInfo) -> Optional[DiagnosticResult]:
        """
        Runs the check against the environment.
        Returns a DiagnosticResult if an issue is found, else None.
        """
        pass
