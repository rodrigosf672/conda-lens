import builtins
import types
from conda_lens.cache_utils import write_cache, cache_path
from conda_lens.migration import PackageResolver, MigrationPlanner
from conda_lens.env_inspect import get_active_env_info


def test_resolver_reads_disk_cache_pypi(monkeypatch):
    write_cache("pypi_search_numpy", "1.2.3")
    PackageResolver.DISK_CACHE_ENABLED = True

    def fail_run(*args, **kwargs):
        raise AssertionError("subprocess.run should not be called when disk cache hit")

    monkeypatch.setattr("subprocess.run", fail_run)
    v = PackageResolver.search_pypi("numpy")
    assert v == "1.2.3"
    PackageResolver.DISK_CACHE_ENABLED = False
    try:
        cache_path("pypi_search_numpy").unlink()
    except Exception:
        pass


def test_resolver_reads_disk_cache_conda_defaults(monkeypatch):
    write_cache("conda_search_numpy_defaults", "1.2.3")
    PackageResolver.DISK_CACHE_ENABLED = True

    def fail_run(*args, **kwargs):
        raise AssertionError("subprocess.run should not be called when disk cache hit")

    monkeypatch.setattr("subprocess.run", fail_run)
    v = PackageResolver.search_conda("numpy")
    assert v == "1.2.3"
    PackageResolver.DISK_CACHE_ENABLED = False
    try:
        cache_path("conda_search_numpy_defaults").unlink()
    except Exception:
        pass


def test_planner_dep_reads_disk_cache(monkeypatch):
    write_cache("deps_pip_asttokens", ["six", "typing-extensions"]) 
    env = get_active_env_info()
    planner = MigrationPlanner(env, use_disk_cache=True)

    def fail_run(*args, **kwargs):
        raise AssertionError("subprocess.run should not be called when disk cache hit")

    monkeypatch.setattr("subprocess.run", fail_run)
    deps = planner._get_pip_dependencies("asttokens")
    assert deps == ["six", "typing-extensions"]
    try:
        cache_path("deps_pip_asttokens").unlink()
    except Exception:
        pass
