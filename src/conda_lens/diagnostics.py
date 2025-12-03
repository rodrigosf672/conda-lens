from typing import List, Type
from .env_inspect import EnvInfo
from .rules import ALL_RULES, BaseRule, DiagnosticResult

def run_diagnostics(env: EnvInfo) -> List[DiagnosticResult]:
    results = []
    for rule_cls in ALL_RULES:
        rule = rule_cls()
        result = rule.check(env)
        if result:
            results.append(result)
    return results
