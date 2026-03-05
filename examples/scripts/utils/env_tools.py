from pathlib import Path
import sys

def add_src_to_syspath():
    p = str(Path('src').resolve())
    if p not in sys.path:
        sys.path.append(p)
    return p

def get_env_summary():
    add_src_to_syspath()
    from conda_lens.env_inspect import get_active_env_info
    env = get_active_env_info()
    # env.packages is Dict[str, List[PackageDetails]]
    pip_count = sum(1 for pkgs in env.packages.values() for x in pkgs if x.manager == "pip")
    conda_count = sum(1 for pkgs in env.packages.values() for x in pkgs if x.manager == "conda")
    return {
        "name": env.name,
        "python": env.python_version,
        "os": env.os_info,
        "pip": pip_count,
        "conda": conda_count,
    }

def list_packages_by_manager(manager: str):
    add_src_to_syspath()
    from conda_lens.env_inspect import get_active_env_info
    env = get_active_env_info()
    # env.packages is Dict[str, List[PackageDetails]]
    return sorted([p.name for pkgs in env.packages.values() for p in pkgs if p.manager == manager])

