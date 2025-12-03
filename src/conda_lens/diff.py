from typing import Dict, List, Tuple
from .env_inspect import EnvInfo, PackageDetails

def diff_envs(env_a: EnvInfo, env_b: EnvInfo) -> Dict[str, List[str]]:
    """
    Compares two environments and returns differences.
    """
    diff_report = {
        "only_in_a": [],
        "only_in_b": [],
        "version_mismatch": []
    }
    
    pkgs_a = env_a.packages
    pkgs_b = env_b.packages
    
    all_keys = set(pkgs_a.keys()) | set(pkgs_b.keys())
    
    for name in sorted(all_keys):
        if name not in pkgs_b:
            diff_report["only_in_a"].append(f"{name}=={pkgs_a[name].version}")
        elif name not in pkgs_a:
            diff_report["only_in_b"].append(f"{name}=={pkgs_b[name].version}")
        else:
            ver_a = pkgs_a[name].version
            ver_b = pkgs_b[name].version
            if ver_a != ver_b:
                diff_report["version_mismatch"].append(
                    f"{name}: {ver_a} -> {ver_b}"
                )
                
    return diff_report
