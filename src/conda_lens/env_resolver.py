"""
Environment resolver for inspecting non-active conda environments.

Provides utilities to:
- Resolve environment names to prefix paths
- Find Python executables in environments
- Load environment information without activation
"""

import json
import subprocess
import platform
from pathlib import Path
from typing import Optional, Dict, Any, List

from .env_inspect import EnvInfo, PackageDetails


class EnvironmentResolverError(Exception):
    """Raised when environment resolution fails."""
    pass


def resolve_env_prefix(env_name: str) -> Path:
    """
    Resolve a conda environment name to its prefix path.
    
    Args:
        env_name: Name of the conda environment
        
    Returns:
        Path to the environment prefix
        
    Raises:
        EnvironmentResolverError: If environment doesn't exist or can't be found
    """
    try:
        # Try JSON output first (most reliable)
        result = subprocess.run(
            ["conda", "env", "list", "--json"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            data = json.loads(result.stdout)
            envs = data.get("envs", [])
            
            # Match by environment name
            for env_path in envs:
                env_path_obj = Path(env_path)
                if env_path_obj.name == env_name:
                    return env_path_obj
            
            raise EnvironmentResolverError(
                f"Environment '{env_name}' not found. "
                f"Available environments: {', '.join([Path(e).name for e in envs])}"
            )
    
    except json.JSONDecodeError:
        pass  # Fall back to table parsing
    except subprocess.TimeoutExpired:
        raise EnvironmentResolverError(f"Timeout while listing conda environments")
    except Exception as e:
        # Fall back to table parsing
        pass
    
    # Fallback: parse table output
    try:
        result = subprocess.run(
            ["conda", "env", "list"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            for line in lines:
                if line.startswith('#') or not line.strip():
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    name = parts[0]
                    path = parts[1] if not parts[1].startswith('*') else parts[2]
                    if name == env_name:
                        return Path(path)
            
            raise EnvironmentResolverError(f"Environment '{env_name}' not found")
    
    except subprocess.TimeoutExpired:
        raise EnvironmentResolverError(f"Timeout while listing conda environments")
    except Exception as e:
        raise EnvironmentResolverError(f"Failed to resolve environment '{env_name}': {e}")
    
    raise EnvironmentResolverError(f"Environment '{env_name}' not found")


def resolve_python(prefix: Path) -> Path:
    """
    Find the Python executable in an environment prefix.
    
    Args:
        prefix: Path to the environment prefix
        
    Returns:
        Path to the Python executable
        
    Raises:
        EnvironmentResolverError: If Python executable not found
    """
    if not prefix.exists():
        raise EnvironmentResolverError(f"Environment prefix does not exist: {prefix}")
    
    # Check common locations
    if platform.system() == "Windows":
        python_paths = [
            prefix / "python.exe",
            prefix / "Scripts" / "python.exe",
        ]
    else:
        python_paths = [
            prefix / "bin" / "python",
            prefix / "bin" / "python3",
        ]
    
    for python_path in python_paths:
        if python_path.exists():
            return python_path
    
    raise EnvironmentResolverError(
        f"Python executable not found in environment: {prefix}"
    )


def load_env_info(prefix: Path, env_name: Optional[str] = None) -> EnvInfo:
    """
    Load environment information for a specific prefix without activation.
    
    Args:
        prefix: Path to the environment prefix
        env_name: Optional name of the environment (for display)
        
    Returns:
        EnvInfo object with environment details
        
    Raises:
        EnvironmentResolverError: If environment inspection fails
    """
    try:
        python_exe = resolve_python(prefix)
    except EnvironmentResolverError as e:
        raise EnvironmentResolverError(f"Failed to load environment: {e}")
    
    # Get Python version
    try:
        result = subprocess.run(
            [str(python_exe), "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        python_version = result.stdout.strip() or result.stderr.strip()
        python_version = python_version.replace("Python ", "")
    except Exception as e:
        python_version = "Unknown"
    
    # Get conda packages
    conda_packages: Dict[str, PackageDetails] = {}
    try:
        result = subprocess.run(
            ["conda", "list", "--prefix", str(prefix), "--json"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            packages_data = json.loads(result.stdout)
            for pkg in packages_data:
                name = pkg.get("name", "")
                if name:
                    conda_packages[name] = PackageDetails(
                        name=name,
                        version=pkg.get("version", "unknown"),
                        manager="conda",
                        build=pkg.get("build", ""),
                        channel=pkg.get("channel", "")
                    )
    except Exception:
        pass  # Continue without conda packages
    
    # Get pip packages
    pip_packages: Dict[str, PackageDetails] = {}
    try:
        result = subprocess.run(
            [str(python_exe), "-m", "pip", "list", "--format=json"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            packages_data = json.loads(result.stdout)
            for pkg in packages_data:
                name = pkg.get("name", "")
                if name and name not in conda_packages:  # Don't duplicate
                    pip_packages[name] = PackageDetails(
                        name=name,
                        version=pkg.get("version", "unknown"),
                        manager="pip"
                    )
    except Exception:
        pass  # Continue without pip packages
    
    # Combine packages
    all_packages = {**conda_packages, **pip_packages}
    
    # Get OS info
    os_info = f"{platform.system()}-{platform.release()}"
    platform_machine = platform.machine()
    
    # GPU info is not available for external envs
    gpu_info = []
    cuda_driver = None
    
    # Determine environment name
    if not env_name:
        env_name = prefix.name
    
    return EnvInfo(
        name=env_name,
        path=str(prefix),
        python_version=python_version,
        packages=all_packages,
        os_info=os_info,
        platform_machine=platform_machine,
        gpu_info=gpu_info,
        cuda_driver_version=cuda_driver
    )
