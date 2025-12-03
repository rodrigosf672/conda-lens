from concurrent.futures import ThreadPoolExecutor
from .env_inspect import get_active_env_info
from .migration import PackageResolver, MigrationPlanner

def warm_cache(parallel: bool = False):
    env = get_active_env_info()
    resolver = PackageResolver(use_disk_cache=True)
    planner = MigrationPlanner(env)
    pkgs = list(env.packages.keys())

    def resolve_one(name: str):
        try:
            resolver.search_pypi(name)
        except Exception:
            pass
        try:
            resolver.search_conda(name)
        except Exception:
            pass
        try:
            resolver.search_uv(name)
        except Exception:
            pass
        try:
            resolver.search_pixi(name)
        except Exception:
            pass
        try:
            planner._get_conda_dependencies(name, env.packages[name].version)
        except Exception:
            pass
        try:
            planner._get_pip_dependencies(name)
        except Exception:
            pass

    if parallel:
        with ThreadPoolExecutor(max_workers=8) as ex:
            list(ex.map(resolve_one, pkgs))
    else:
        for name in pkgs:
            resolve_one(name)

    resolver.cache.save()
