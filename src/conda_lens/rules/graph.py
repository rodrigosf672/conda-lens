from typing import List, Dict, Set
from .base import BaseRule, DiagnosticResult
from ..env_inspect import EnvInfo
from packaging.requirements import Requirement

class GraphRule(BaseRule):
    @property
    def name(self) -> str:
        return "Dependency Graph Cycle Check"

    def check(self, env: EnvInfo) -> DiagnosticResult | None:
        """
        Checks for:
        G-1: Cycles in the dependency graph.
        """
        # Build simple graph: name -> [dep_names]
        adj: Dict[str, Set[str]] = {}
        all_pkgs = [p for sublist in env.packages.values() for p in sublist]
        
        for pkg in all_pkgs:
            name = pkg.name.lower()
            if name not in adj:
                adj[name] = set()
            
            for dep in pkg.depends:
                dep_name = None
                try:
                    dep_name = Requirement(dep).name
                except:
                    parts = dep.split()
                    if len(parts) >= 1:
                        dep_name = parts[0]
                
                if dep_name:
                    d_key = dep_name.lower()
                    # Only add edge if dep is actually installed (ignores missing deps)
                    if d_key in env.packages:
                        adj[name].add(d_key)

        # Detect cycles (DFS)
        visited = set()
        stack = set()
        cycles = []
        
        def visit(n, path):
            if n in stack:
                # Cycle detected
                cycle_path = path[path.index(n):] + [n]
                cycles.append(" -> ".join(cycle_path))
                return
            if n in visited:
                return

            visited.add(n)
            stack.add(n)
            path.append(n)
            
            for neighbor in adj.get(n, []):
                visit(neighbor, path)
            
            path.pop()
            stack.remove(n)

        for node in list(adj.keys()):
            if node not in visited:
                visit(node, [])
                if len(cycles) > 3: # Limit number of cycles reported
                    break
        
        if cycles:
            # Cycles are actually somewhat common in Python ecosystem (e.g. sphinx extensions).
            # So severity might be "INFO" or "WARNING" rather than "ERROR".
            return DiagnosticResult(
                rule_name=self.name,
                severity="INFO", 
                message=f"Found {len(cycles)} dependency cycles (circular dependencies):\n" + "\n".join(cycles[:3]) + ("\n..." if len(cycles) > 3 else ""),
                suggestion="Cycles are often benign in Python but can cause installation issues. Check if these are expected."
            )
        return None
