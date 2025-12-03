import json
import time
from pathlib import Path
from typing import Dict, Any, Optional

CACHE_DIR = Path.home() / ".cache" / "conda-lens"
CACHE_FILE = CACHE_DIR / "deps.json"

_cache_mem: Dict[str, Any] = {}
_loaded = False

def _now() -> float:
    return time.time()

def cache_path() -> Path:
    return CACHE_FILE

def load_cache() -> Dict[str, Any]:
    global _loaded, _cache_mem
    if _loaded:
        return _cache_mem
    try:
        if CACHE_FILE.exists():
            _cache_mem = json.loads(CACHE_FILE.read_text())
    except Exception:
        _cache_mem = {}
    _loaded = True
    return _cache_mem

def save_cache(cache: Optional[Dict[str, Any]] = None) -> None:
    global _cache_mem
    data = cache or _cache_mem
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(json.dumps(data))
    except Exception:
        pass

def get_cached_deps(pkg: str) -> Optional[Dict[str, Any]]:
    cache = load_cache()
    return cache.get(pkg)

def set_cached_deps(pkg: str, deps: Any, resolved: bool = True) -> None:
    cache = load_cache()
    cache[pkg] = {
        "resolved": bool(resolved),
        "deps": deps if deps is not None else [],
        "timestamp": _now()
    }
    save_cache(cache)

def is_stale(entry: Dict[str, Any], max_age_seconds: int = 24 * 3600) -> bool:
    try:
        ts = float(entry.get("timestamp") or 0)
        return (_now() - ts) > max_age_seconds
    except Exception:
        return True

class CacheManager:
    def __init__(self):
        self.data: Dict[str, Any] = {}

    def load(self) -> Dict[str, Any]:
        self.data = load_cache()
        return self.data

    def save(self) -> None:
        save_cache(self.data)

    def clear(self) -> None:
        self.data = {}
        save_cache(self.data)

    def stats(self) -> Dict[str, Any]:
        data = self.data or load_cache()
        total = len(data)
        stale = 0
        for k, v in data.items():
            if is_stale(v):
                stale += 1
        return {
            "total": total,
            "stale": stale,
            "fresh": total - stale,
            "path": str(CACHE_FILE)
        }

def refresh_cache(full: bool = False, incremental: bool = False):
    from .env_inspect import get_active_env_info
    from .migration import MigrationPlanner, PackageResolver, run_with_timeout
    env = get_active_env_info()
    planner = MigrationPlanner(env)
    cache = load_cache()
    names = list(env.packages.keys())
    for name in names:
        entry = cache.get(name)
        if not full and incremental and entry and not is_stale(entry):
            continue
        deps = []
        pkg = env.packages[name]
        if pkg.manager == "conda":
            deps = planner._get_conda_dependencies(name, pkg.version)
        elif pkg.manager == "pip":
            deps = planner._get_pip_dependencies(name)
        if deps == PackageResolver.TIMEOUT:
            deps = []
        set_cached_deps(name, deps, resolved=True)
    build_graphs()

def build_graphs():
    cache = load_cache()
    dep_graph: Dict[str, Any] = {}
    rev_graph: Dict[str, Any] = {}
    for name, entry in cache.items():
        deps = entry.get("deps") or []
        dep_graph[name] = [d.lower().split()[0] for d in deps if d]
    for name, deps in dep_graph.items():
        for d in deps:
            rev_graph.setdefault(d, []).append(name)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    (CACHE_DIR / "dep-graph.json").write_text(json.dumps(dep_graph))
    (CACHE_DIR / "rev-graph.json").write_text(json.dumps(rev_graph))

def update_cache():
    from .env_inspect import get_active_env_info
    from .migration import MigrationPlanner, PackageResolver
    env = get_active_env_info()
    planner = MigrationPlanner(env)
    cache = load_cache()
    for name in list(env.packages.keys()):
        entry = cache.get(name)
        if entry and not is_stale(entry):
            continue
        deps = []
        pkg = env.packages[name]
        if pkg.manager == "conda":
            deps = planner._get_conda_dependencies(name, pkg.version)
        elif pkg.manager == "pip":
            deps = planner._get_pip_dependencies(name)
        if deps == PackageResolver.TIMEOUT:
            deps = []
        set_cached_deps(name, deps, resolved=True)
    build_graphs()
