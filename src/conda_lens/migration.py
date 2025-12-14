"""
Package manager migration planner and executor.
Safely migrate packages between pip, conda, and uv.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Set
from enum import Enum
import subprocess
import json
from pathlib import Path
import logging
import os
import sys
from .cache import load_cache, save_cache, get_cached_deps, set_cached_deps, is_stale
from .cache_utils import read_cache, write_cache
from .env_inspect import EnvInfo, PackageDetails


class SafetyStatus(Enum):
    OK = "OK"
    CONFLICT = "Conflict"
    UNSUPPORTED = "Unsupported"
    MISSING = "Missing"
    PYTHON_VERSION = "Python Version Mismatch"
    CUDA_RISK = "CUDA Build Risk"
    TIMEOUT = "Timeout"


@dataclass
class MigrationStep:
    """Represents a single package migration operation."""
    package_name: str
    current_manager: str
    current_version: str
    target_manager: str
    target_version: Optional[str]
    safety_status: SafetyStatus
    reason: str
    dependencies: List[str]
    
    def is_safe(self) -> bool:
        """Check if this migration step is safe to execute."""
        return self.safety_status == SafetyStatus.OK


@dataclass
class MigrationReport:
    """Summary report of a migration plan."""
    total_packages: int
    safe_to_migrate: int
    conflicts: int
    unsupported: int
    missing: int
    steps: List[MigrationStep]
    
    def can_proceed(self) -> bool:
        """Check if migration can proceed safely."""
        return self.conflicts == 0 and self.missing == 0


logger = logging.getLogger("conda_lens")

def _setup_debug_logger():
    if os.environ.get("CONDA_LENS_DEBUG") == "1":
        logger.setLevel(logging.DEBUG)
        if not logger.handlers:
            h = logging.StreamHandler(sys.stdout)
            h.setLevel(logging.DEBUG)
            fmt = logging.Formatter("[%(levelname)s] %(message)s")
            h.setFormatter(fmt)
            logger.addHandler(h)

_setup_debug_logger()

def _trunc(val) -> str:
    try:
        if isinstance(val, bytes):
            try:
                val = val.decode(errors="ignore")
            except Exception:
                val = str(val)
        elif not isinstance(val, str):
            val = "" if val is None else str(val)
        return val[:300]
    except Exception:
        return ""

def run_with_timeout(func, *args, timeout=3, **kwargs):
    try:
        kwargs["timeout"] = timeout
        return func(*args, **kwargs)
    except subprocess.TimeoutExpired:
        return PackageResolver.TIMEOUT

class PackageResolver:
    """Resolve package availability across different package managers."""
    
    # Cache to avoid repeated searches
    _cache: Dict[str, Optional[str]] = {}
    TIMEOUT = "__TIMEOUT__"
    DISK_CACHE_ENABLED = False

    def __init__(self, use_disk_cache: bool = False):
        if use_disk_cache:
            PackageResolver.DISK_CACHE_ENABLED = True
    from .cache import CacheManager as _CacheManager
    cache = _CacheManager()
    
    @staticmethod
    def search_conda(package_name: str, channel: Optional[str] = None) -> Optional[str]:
        """Search for package in conda repositories (optimized)."""
        cache_key = f"conda:{channel or 'default'}:{package_name}"
        if cache_key in PackageResolver._cache:
            logger.info(f"INFO: Using cached resolver result for {package_name} from conda")
            return PackageResolver._cache[cache_key]
        dk = f"conda_search_{package_name}_{channel or 'defaults'}"
        if PackageResolver.DISK_CACHE_ENABLED:
            cached = read_cache(dk)
            if cached is not None:
                logger.info(f"INFO: Using cached resolver result for {package_name} from conda")
                return cached
        
        try:
            # Use faster conda list --json if package might be installed
            # Otherwise fall back to conda search
            cmd = ["conda", "list", package_name, "--json"]
            logger.debug(f"[resolver] running: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=6)
            logger.debug(f"[resolver] returncode={result.returncode}")
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                if data:
                    version = data[0]["version"]
                    PackageResolver._cache[cache_key] = version
                    if PackageResolver.DISK_CACHE_ENABLED:
                        write_cache(dk, version)
                    return version
            
            # Fall back to search (slower)
            cmd = ["conda", "search", package_name, "--json", "--override-channels"]
            if channel:
                cmd.extend(["-c", channel])
            else:
                cmd.extend(["-c", "defaults"])
            
            logger.debug(f"[resolver] running: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=6)
            logger.debug(f"[resolver] returncode={result.returncode}")
            if result.returncode == 0:
                data = json.loads(result.stdout)
                if package_name in data and data[package_name]:
                    version = data[package_name][-1]["version"]
                    PackageResolver._cache[cache_key] = version
                    if PackageResolver.DISK_CACHE_ENABLED:
                        write_cache(dk, version)
                    return version
        except subprocess.TimeoutExpired:
            logger.debug("[resolver] timeout after 6s")
            PackageResolver._cache[cache_key] = None
            return None
        except (json.JSONDecodeError, KeyError, IndexError):
            pass
        
        PackageResolver._cache[cache_key] = None
        if PackageResolver.DISK_CACHE_ENABLED:
            write_cache(dk, None)
        return None
    
    @staticmethod
    def search_pypi(package_name: str) -> Optional[str]:
        """Search for package on PyPI (optimized)."""
        cache_key = f"pypi:{package_name}"
        if cache_key in PackageResolver._cache:
            logger.info(f"INFO: Using cached resolver result for {package_name} from pip")
            return PackageResolver._cache[cache_key]
        
        try:
            dk = f"pypi_search_{package_name}"
            if PackageResolver.DISK_CACHE_ENABLED:
                cached = read_cache(dk)
                if cached is not None:
                    logger.info(f"INFO: Using cached resolver result for {package_name} from pip")
                    return cached
            # Use pip show first (faster for installed packages)
            logger.debug("[resolver] running: pip show %s" % package_name)
            result = subprocess.run(
                ["pip", "show", package_name],
                capture_output=True,
                text=True,
                timeout=6
            )
            logger.debug(f"[resolver] returncode={result.returncode}")
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if line.startswith("Version:"):
                        version = line.split(":", 1)[1].strip()
                        PackageResolver._cache[cache_key] = version
                        if PackageResolver.DISK_CACHE_ENABLED:
                            write_cache(dk, version)
                        return version
            
            # Fall back to pip index (slower)
            logger.debug("[resolver] running: pip index versions %s" % package_name)
            result = subprocess.run(
                ["pip", "index", "versions", package_name],
                capture_output=True,
                text=True,
                timeout=6
            )
            logger.debug(f"[resolver] returncode={result.returncode}")
            if result.returncode == 0:
                logger.debug("[resolver] pip index returned version list")
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if "Available versions:" in line:
                        versions = line.split(":")[-1].strip().split(",")
                        if versions:
                            version = versions[0].strip()
                            PackageResolver._cache[cache_key] = version
                            if PackageResolver.DISK_CACHE_ENABLED:
                                write_cache(dk, version)
                            return version
        except subprocess.TimeoutExpired:
            logger.debug("[resolver] timeout after 6s")
            PackageResolver._cache[cache_key] = None
            return None
        
        PackageResolver._cache[cache_key] = None
        if PackageResolver.DISK_CACHE_ENABLED:
            write_cache(dk, None)
        return None
    
    @staticmethod
    def search_uv(package_name: str) -> Optional[str]:
        """Search for package using uv (optimized)."""
        cache_key = f"uv:{package_name}"
        if cache_key in PackageResolver._cache:
            logger.info(f"INFO: Using cached resolver result for {package_name} from uv")
            return PackageResolver._cache[cache_key]
        
        try:
            dk = f"uv_search_{package_name}"
            if PackageResolver.DISK_CACHE_ENABLED:
                cached = read_cache(dk)
                if cached is not None:
                    logger.info(f"INFO: Using cached resolver result for {package_name} from uv")
                    return cached
            logger.debug("[resolver] running: uv pip show %s" % package_name)
            result = subprocess.run(
                ["uv", "pip", "show", package_name],
                capture_output=True,
                text=True,
                timeout=6
            )
            logger.debug(f"[resolver] returncode={result.returncode}")
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if line.startswith("Version:"):
                        version = line.split(":", 1)[1].strip()
                        PackageResolver._cache[cache_key] = version
                        if PackageResolver.DISK_CACHE_ENABLED:
                            write_cache(dk, version)
                        return version
        except subprocess.TimeoutExpired:
            logger.debug("[resolver] timeout after 6s")
            PackageResolver._cache[cache_key] = None
            return None
        except FileNotFoundError:
            pass
        
        PackageResolver._cache[cache_key] = None
        if PackageResolver.DISK_CACHE_ENABLED:
            write_cache(dk, None)
        return None
    
    @staticmethod
    def search_pixi(package_name: str, channel: Optional[str] = None) -> Optional[str]:
        """Search for package using pixi (conda-based)."""
        cache_key = f"pixi:{channel or 'default'}:{package_name}"
        if cache_key in PackageResolver._cache:
            logger.info(f"INFO: Using cached resolver result for {package_name} from pixi")
            return PackageResolver._cache[cache_key]
        
        try:
            dk = f"pixi_search_{package_name}_{channel or 'defaults'}"
            if PackageResolver.DISK_CACHE_ENABLED:
                cached = read_cache(dk)
                if cached is not None:
                    logger.info(f"INFO: Using cached resolver result for {package_name} from pixi")
                    return cached
            # Pixi uses conda channels, so search conda repos
            cmd = ["pixi", "search", package_name, "--json"]
            if channel:
                cmd.extend(["-c", channel])
            
            logger.debug(f"[resolver] running: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=6)
            if result.returncode == 0:
                data = json.loads(result.stdout)
                if data and len(data) > 0:
                    # Get latest version from search results
                    version = data[0].get("version")
                    if version:
                        PackageResolver._cache[cache_key] = version
                        if PackageResolver.DISK_CACHE_ENABLED:
                            write_cache(dk, version)
                        return version
        except subprocess.TimeoutExpired:
            logger.debug("[resolver] timeout after 6s")
            PackageResolver._cache[cache_key] = None
            return None
        except (json.JSONDecodeError, FileNotFoundError, KeyError, IndexError):
            pass
        
        # Fall back to conda search since pixi uses conda packages
        return PackageResolver.search_conda(package_name, channel)
    
    @staticmethod
    def clear_cache():
        """Clear the resolution cache."""
        PackageResolver._cache.clear()


class MigrationPlanner:
    """Plan and execute package manager migrations."""
    
    def __init__(self, env_info: EnvInfo, use_disk_cache: bool = False):
        self.env_info = env_info
        self.resolver = PackageResolver(use_disk_cache=use_disk_cache)
        self.rollback_file = Path.home() / ".conda-lens" / "rollback.json"
        self.rollback_file.parent.mkdir(exist_ok=True)
        self.log_file = Path.home() / ".conda-lens" / "migrations.log"
        self.last_error: Optional[str] = None
    
    def plan_migration(
        self,
        target_manager: str,
        packages: Optional[List[str]] = None,
        channel: Optional[str] = None
    ) -> MigrationReport:
        """
        Plan migration to target package manager.
        
        Args:
            target_manager: Target package manager (conda, pip, uv)
            packages: Specific packages to migrate (None = all)
            channel: Target channel for conda (e.g., conda-forge)
        
        Returns:
            MigrationReport with planned steps
        """
        steps = []
        logger.debug("[migration] building dependency graphs")
        dep_graph = self._build_dependency_graph()
        rev_graph = self._build_reverse_dependency_graph(dep_graph)
        
        # Filter packages to migrate
        if packages:
            # Flatten
            all_pkgs = [p for sublist in self.env_info.packages.values() for p in sublist]
            packages_to_check = [
                p for p in all_pkgs if p.name in packages
            ]
        else:
            packages_to_check = [p for sublist in self.env_info.packages.values() for p in sublist]
        
        for pkg in packages_to_check:
            logger.debug(f"[migration] analyzing package {pkg.name}")
            # Skip if already using target manager
            if pkg.manager == target_manager:
                continue
            ok, group, reason = self._check_dependents(pkg.name, target_manager, channel, dep_graph, rev_graph)
            if not ok:
                steps.append(MigrationStep(
                    package_name=pkg.name,
                    current_manager=pkg.manager,
                    current_version=pkg.version,
                    target_manager=target_manager,
                    target_version=None,
                    safety_status=SafetyStatus.CONFLICT,
                    reason=reason or "Blocked by dependency chain",
                    dependencies=dep_graph.get(pkg.name, [])
                ))
                continue
            # Retrieve list of packages for the group name
            # If multiple versions exist, we pick the one matching the group logic ideally.
            # But here group contains names.
            group_pkgs = []
            for n in group:
                if n in self.env_info.packages:
                    # Take all instances for now
                    group_pkgs.extend(self.env_info.packages[n])
            for gp in group_pkgs:
                s = self._analyze_package(gp, target_manager, channel)
                steps.append(s)
        
        # Calculate summary
        safe_count = sum(1 for s in steps if s.is_safe())
        conflict_count = sum(1 for s in steps if s.safety_status == SafetyStatus.CONFLICT)
        unsupported_count = sum(1 for s in steps if s.safety_status == SafetyStatus.UNSUPPORTED)
        missing_count = sum(1 for s in steps if s.safety_status == SafetyStatus.MISSING)
        
        return MigrationReport(
            total_packages=len(steps),
            safe_to_migrate=safe_count,
            conflicts=conflict_count,
            unsupported=unsupported_count,
            missing=missing_count,
            steps=steps
        )

    def verify_manager_available(self, manager: str) -> bool:
        try:
            if manager == "conda":
                r = subprocess.run(["conda", "--version"], capture_output=True, text=True)
                return r.returncode == 0
            if manager == "pip":
                r = subprocess.run(["pip", "--version"], capture_output=True, text=True)
                return r.returncode == 0
            if manager == "uv":
                r = subprocess.run(["uv", "--version"], capture_output=True, text=True)
                return r.returncode == 0
            if manager == "pixi":
                r = subprocess.run(["pixi", "--version"], capture_output=True, text=True)
                return r.returncode == 0
        except Exception:
            return False
        return False
    
    def _analyze_package(
        self,
        pkg: PackageDetails,
        target_manager: str,
        channel: Optional[str] = None
    ) -> MigrationStep:
        """Analyze a single package for migration."""
        
        # Search for package in target manager
        target_version = None
        if target_manager == "conda":
            target_version = self.resolver.search_conda(pkg.name, channel)
        elif target_manager == "pip":
            target_version = self.resolver.search_pypi(pkg.name)
        elif target_manager == "uv":
            target_version = self.resolver.search_uv(pkg.name)
        elif target_manager == "pixi":
            target_version = self.resolver.search_pixi(pkg.name, channel)
        
        # Determine safety status
        if target_version == PackageResolver.TIMEOUT:
            return MigrationStep(
                package_name=pkg.name,
                current_manager=pkg.manager,
                current_version=pkg.version,
                target_manager=target_manager,
                target_version=None,
                safety_status=SafetyStatus.TIMEOUT,
                reason="Resolution timed out",
                dependencies=[]
            )
        if target_version is None:
            return MigrationStep(
                package_name=pkg.name,
                current_manager=pkg.manager,
                current_version=pkg.version,
                target_manager=target_manager,
                target_version=None,
                safety_status=SafetyStatus.MISSING,
                reason=f"Package not found in {target_manager}",
                dependencies=[]
            )
        
        if pkg.build and ("cuda" in pkg.build.lower() or "cu" in pkg.build.lower()):
            return MigrationStep(
                package_name=pkg.name,
                current_manager=pkg.manager,
                current_version=pkg.version,
                target_manager=target_manager,
                target_version=target_version,
                safety_status=SafetyStatus.CUDA_RISK,
                reason="Package has CUDA-specific build",
                dependencies=[]
            )
        
        if target_version != pkg.version:
            return MigrationStep(
                package_name=pkg.name,
                current_manager=pkg.manager,
                current_version=pkg.version,
                target_manager=target_manager,
                target_version=target_version,
                safety_status=SafetyStatus.CONFLICT,
                reason=f"Version mismatch: {pkg.version} → {target_version}",
                dependencies=[]
            )
        
        # All checks passed
        return MigrationStep(
            package_name=pkg.name,
            current_manager=pkg.manager,
            current_version=pkg.version,
            target_manager=target_manager,
            target_version=target_version,
            safety_status=SafetyStatus.OK,
            reason="Safe to migrate",
            dependencies=[]
        )

    def _build_dependency_graph(self) -> Dict[str, List[str]]:
        graph: Dict[str, List[str]] = {}
        names = list(self.env_info.packages.keys())
        for name in names:
            # For graph building, if strictly name-based, we have ambiguity if multiple installed.
            # We'll use the first one or prefer conda to avoid cycles or complexity for now.
            pkgs = self.env_info.packages[name]
            # Prefer conda
            pkg = next((p for p in pkgs if p.manager == "conda"), pkgs[0])
            logger.debug(f"[migration] resolving dependencies for {name}")
            cached = get_cached_deps(name)
            deps: List[str] = []
            if cached and not is_stale(cached):
                deps = cached.get("deps") or []
                logger.debug(f"[migration] resolved deps for {name}: {len(deps)} items (cached)")
            else:
                if pkg.manager == "conda":
                    deps = self._get_conda_dependencies(name, pkg.version)
                elif pkg.manager == "pip":
                    deps = self._get_pip_dependencies(name)
                if deps == PackageResolver.TIMEOUT:
                    logger.debug(f"[migration] dependency resolution timed out for {name}")
                    deps = []
                set_cached_deps(name, deps, resolved=True)
                logger.debug(f"[migration] resolved deps for {name}: {len(deps)} items")
            graph[name] = [d.lower().split()[0] for d in deps if d]
        return graph

    def _build_reverse_dependency_graph(self, graph: Dict[str, List[str]]) -> Dict[str, List[str]]:
        rev: Dict[str, List[str]] = {k: [] for k in graph.keys()}
        for src, deps in graph.items():
            for d in deps:
                if d not in rev:
                    rev[d] = []
                if src not in rev[d]:
                    rev[d].append(src)
        return rev

    def _get_conda_dependencies(self, name: str, version: Optional[str]) -> List[str]:
        try:
            dkey = f"deps_conda_{name}"
            dc = read_cache(dkey)
            if dc is not None:
                return dc
            cached = get_cached_deps(name)
            if cached and not is_stale(cached):
                deps = cached.get("deps") or []
                write_cache(dkey, deps)
                return deps
            cmd = ["conda", "search", name, "--json"]
            result = run_with_timeout(subprocess.run, cmd, capture_output=True, text=True, timeout=6)
            if result is PackageResolver.TIMEOUT:
                return PackageResolver.TIMEOUT
            if result.returncode == 0:
                data = json.loads(result.stdout)
                if name in data:
                    records = data[name]
                    match = None
                    if version:
                        for r in records:
                            if r.get("version") == version:
                                match = r
                                break
                    if not match and records:
                        match = records[-1]
                    if match and "depends" in match:
                        deps = match.get("depends") or []
                        set_cached_deps(name, deps, resolved=True)
                        write_cache(dkey, deps)
                        return deps
        except Exception:
            pass
        return []

    def _get_pip_dependencies(self, name: str) -> List[str]:
        try:
            dkey = f"deps_pip_{name}"
            dc = read_cache(dkey)
            if dc is not None:
                return dc
            cached = get_cached_deps(name)
            if cached and not is_stale(cached):
                deps = cached.get("deps") or []
                write_cache(dkey, deps)
                return deps
            logger.debug("[migration] resolving pip dependencies for %s" % name)
            result = run_with_timeout(subprocess.run, ["pip", "show", name], capture_output=True, text=True, timeout=6)
            if result is PackageResolver.TIMEOUT:
                return PackageResolver.TIMEOUT
            if result.returncode == 0:
                lines = result.stdout.splitlines()
                for line in lines:
                    if line.startswith("Requires:"):
                        val = line.split(":", 1)[1].strip()
                        if not val:
                            deps: List[str] = []
                            set_cached_deps(name, deps, resolved=True)
                            write_cache(dkey, deps)
                            return deps
                        deps = [x.strip() for x in val.split(",") if x.strip()]
                        set_cached_deps(name, deps, resolved=True)
                        write_cache(dkey, deps)
                        return deps
        except Exception:
            pass
        return []

    def _collect_upstream_dependents(self, name: str, rev_graph: Dict[str, List[str]]) -> List[str]:
        visited: Set[str] = set()
        stack = [name]
        out: List[str] = []
        while stack:
            n = stack.pop()
            for d in rev_graph.get(n, []):
                if d not in visited:
                    visited.add(d)
                    out.append(d)
                    stack.append(d)
        return out

    def _check_dependents(
        self,
        name: str,
        target_manager: str,
        channel: Optional[str],
        dep_graph: Dict[str, List[str]],
        rev_graph: Dict[str, List[str]]
    ) -> (bool, List[str], Optional[str]):
        dependents = self._collect_upstream_dependents(name, rev_graph)
        group = [name] + dependents
        for d in dependents:
            tv = None
            if target_manager == "conda":
                tv = self.resolver.search_conda(d, channel)
            elif target_manager == "pip":
                tv = self.resolver.search_pypi(d)
            elif target_manager == "uv":
                tv = self.resolver.search_uv(d)
            elif target_manager == "pixi":
                tv = self.resolver.search_pixi(d, channel)
            if tv is None:
                return False, group, f"Dependent {d} not available on {target_manager}"
            for sub in dep_graph.get(d, []):
                sv = None
                if target_manager == "conda":
                    sv = self.resolver.search_conda(sub, channel)
                elif target_manager == "pip":
                    sv = self.resolver.search_pypi(sub)
                elif target_manager == "uv":
                    sv = self.resolver.search_uv(sub)
                elif target_manager == "pixi":
                    sv = self.resolver.search_pixi(sub, channel)
                if sv is None:
                    return False, group, f"Dependency {sub} of {d} not available on {target_manager}"
        ordered = self._toposort(group, dep_graph)
        return True, ordered, None

    def _toposort(self, pkgs: List[str], dep_graph: Dict[str, List[str]]) -> List[str]:
        subset = set(pkgs)
        indeg: Dict[str, int] = {p: 0 for p in subset}
        adj: Dict[str, List[str]] = {p: [] for p in subset}
        for p in subset:
            for d in dep_graph.get(p, []):
                if d in subset:
                    indeg[p] += 1
                    adj.setdefault(d, []).append(p)
        queue = [p for p in subset if indeg[p] == 0]
        order: List[str] = []
        processed: Set[str] = set()
        while queue:
            n = queue.pop()
            order.append(n)
            processed.add(n)
            for v in adj.get(n, []):
                if v in processed:
                    continue
                indeg[v] -= 1
                if indeg[v] == 0:
                    queue.append(v)
        if len(order) != len(subset):
            blocked = [p for p in subset if p not in set(order)]
            logger.debug(f"[migration] cycle detected, blocked nodes: {blocked}")
            return order
        return order
    
    def execute_migration(
        self,
        report: MigrationReport,
        dry_run: bool = True
    ) -> Dict[str, bool]:
        """
        Execute migration plan.
        
        Args:
            report: Migration report from plan_migration
            dry_run: If True, don't actually execute
        
        Returns:
            Dict mapping package names to success status
        """
        if dry_run:
            return {step.package_name: True for step in report.steps}
        
        results = {}
        rollback_data = []
        executed: List[Dict[str, str]] = []
        
        for step in report.steps:
            if not step.is_safe():
                results[step.package_name] = False
                continue
            
            self.last_error = None
            success = self._migrate_package(step)
            results[step.package_name] = success
            
            if success:
                rollback_data.append({
                    "package": step.package_name,
                    "from_manager": step.current_manager,
                    "from_version": step.current_version,
                    "to_manager": step.target_manager,
                    "to_version": step.target_version
                })
                executed.append(rollback_data[-1])
            else:
                for op in reversed(executed):
                    try:
                        if op["to_manager"] == "conda":
                            subprocess.run(["conda", "remove", "-y", op["package"]], check=True, capture_output=True)
                        elif op["to_manager"] == "pip":
                            subprocess.run(["pip", "uninstall", "-y", op["package"]], check=True, capture_output=True)
                        elif op["to_manager"] == "pixi":
                            subprocess.run(["pixi", "remove", op["package"]], check=True, capture_output=True)
                        if op["from_manager"] == "conda":
                            subprocess.run(["conda", "install", "-y", f"{op['package']}=={op['from_version']}"], check=True, capture_output=True)
                        elif op["from_manager"] == "pip":
                            subprocess.run(["pip", "install", f"{op['package']}=={op['from_version']}"], check=True, capture_output=True)
                    except subprocess.CalledProcessError:
                        pass
                return results
        
        # Save rollback data
        if rollback_data:
            self._save_rollback(rollback_data)
        
        try:
            refreshed = self.env_info.__class__(
                name=self.env_info.name,
                path=self.env_info.path,
                python_version=self.env_info.python_version,
                os_info=self.env_info.os_info,
                platform_machine=self.env_info.platform_machine,
                packages=self.env_info.packages,
                cuda_driver_version=self.env_info.cuda_driver_version,
                gpu_info=self.env_info.gpu_info
            )
            env = refreshed
            env = __import__('conda_lens.env_inspect', fromlist=['']).get_active_env_info()
            for op in rollback_data:
                cur = env.packages.get(op["package"])
                if not cur or cur.manager != op["to_manager"]:
                    for rop in reversed(rollback_data):
                        try:
                            if rop["to_manager"] == "conda":
                                subprocess.run(["conda", "remove", "-y", rop["package"]], check=True, capture_output=True)
                            elif rop["to_manager"] == "pip":
                                subprocess.run(["pip", "uninstall", "-y", rop["package"]], check=True, capture_output=True)
                            elif rop["to_manager"] == "pixi":
                                subprocess.run(["pixi", "remove", rop["package"]], check=True, capture_output=True)
                            if rop["from_manager"] == "conda":
                                subprocess.run(["conda", "install", "-y", f"{rop['package']}=={rop['from_version']}"], check=True, capture_output=True)
                            elif rop["from_manager"] == "pip":
                                subprocess.run(["pip", "install", f"{rop['package']}=={rop['from_version']}"], check=True, capture_output=True)
                        except subprocess.CalledProcessError:
                            continue
                    break
        except Exception:
            pass
        
        return results

    def _write_log(self, text: str):
        try:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.log_file, 'a') as f:
                f.write(text + "\n")
        except Exception:
            pass
    
    def _migrate_package(self, step: MigrationStep) -> bool:
        """Migrate a single package."""
        try:
            # Uninstall from current manager
            if step.current_manager == "conda":
                logger.info(f"subprocess: conda remove -y {step.package_name}")
                subprocess.run(
                    ["conda", "remove", "-y", step.package_name],
                    check=True,
                    capture_output=True
                )
            elif step.current_manager == "pip":
                logger.info(f"subprocess: pip uninstall -y {step.package_name}")
                subprocess.run(
                    ["pip", "uninstall", "-y", step.package_name],
                    check=True,
                    capture_output=True
                )
            elif step.current_manager == "pixi":
                logger.info(f"subprocess: pixi remove {step.package_name}")
                subprocess.run(
                    ["pixi", "remove", step.package_name],
                    check=True,
                    capture_output=True
                )
            
            # Install with target manager
            if step.target_manager == "conda":
                logger.info(f"subprocess: conda install -y {step.package_name}=={step.target_version}")
                subprocess.run(
                    ["conda", "install", "-y", f"{step.package_name}=={step.target_version}"],
                    check=True,
                    capture_output=True
                )
            elif step.target_manager == "pip":
                logger.info(f"subprocess: pip install {step.package_name}=={step.target_version}")
                subprocess.run(
                    ["pip", "install", f"{step.package_name}=={step.target_version}"],
                    check=True,
                    capture_output=True
                )
            elif step.target_manager == "uv":
                logger.info(f"subprocess: uv pip install {step.package_name}=={step.target_version}")
                subprocess.run(
                    ["uv", "pip", "install", f"{step.package_name}=={step.target_version}"],
                    check=True,
                    capture_output=True
                )
            elif step.target_manager == "pixi":
                logger.info(f"subprocess: pixi add {step.package_name}=={step.target_version}")
                subprocess.run(
                    ["pixi", "add", f"{step.package_name}=={step.target_version}"],
                    check=True,
                    capture_output=True
                )
            
            return True
        except subprocess.CalledProcessError as e:
            self.last_error = (e.stderr or "") or (e.stdout or "") or str(e)
            logger.error(self.last_error[:300])
            self._write_log(f"FAIL {step.package_name} {step.current_manager}->{step.target_manager}: {self.last_error}")
            self._rollback_package(step)
            return False
    
    def _rollback_package(self, step: MigrationStep):
        """Rollback a failed migration."""
        try:
            # Reinstall original package
            if step.current_manager == "conda":
                subprocess.run(
                    ["conda", "install", "-y", f"{step.package_name}=={step.current_version}"],
                    check=True,
                    capture_output=True
                )
            elif step.current_manager == "pip":
                subprocess.run(
                    ["pip", "install", f"{step.package_name}=={step.current_version}"],
                    check=True,
                    capture_output=True
                )
        except subprocess.CalledProcessError:
            pass  # Best effort rollback
    
    def _save_rollback(self, data: List[Dict]):
        """Save rollback data to file."""
        existing = []
        if self.rollback_file.exists():
            with open(self.rollback_file) as f:
                existing = json.load(f)
        
        existing.append({
            "timestamp": __import__('datetime').datetime.now().isoformat(),
            "operations": data
        })
        
        with open(self.rollback_file, 'w') as f:
            json.dump(existing, f, indent=2)
    
    def undo_last_migration(self) -> bool:
        """Undo the most recent migration."""
        if not self.rollback_file.exists():
            return False
        
        with open(self.rollback_file) as f:
            rollback_history = json.load(f)
        
        if not rollback_history:
            return False
        
        last_migration = rollback_history.pop()
        
        # Reverse each operation
        for op in reversed(last_migration["operations"]):
            try:
                # Uninstall current
                if op["to_manager"] == "conda":
                    subprocess.run(
                        ["conda", "remove", "-y", op["package"]],
                        check=True,
                        capture_output=True
                    )
                elif op["to_manager"] == "pip":
                    subprocess.run(
                        ["pip", "uninstall", "-y", op["package"]],
                        check=True,
                        capture_output=True
                    )
                
                # Reinstall original
                if op["from_manager"] == "conda":
                    subprocess.run(
                        ["conda", "install", "-y", f"{op['package']}=={op['from_version']}"],
                        check=True,
                        capture_output=True
                    )
                elif op["from_manager"] == "pip":
                    subprocess.run(
                        ["pip", "install", f"{op['package']}=={op['from_version']}"],
                        check=True,
                        capture_output=True
                    )
            except subprocess.CalledProcessError:
                continue
        
        # Update rollback file
        with open(self.rollback_file, 'w') as f:
            json.dump(rollback_history, f, indent=2)
        
        return True
