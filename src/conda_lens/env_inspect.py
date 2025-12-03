import json
import platform
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
try:
    import pynvml
    HAS_PYNVML = True
except ImportError:
    HAS_PYNVML = False

@dataclass
class PackageDetails:
    name: str
    version: str
    build: Optional[str] = None
    channel: Optional[str] = None
    manager: str = "unknown"  # 'conda' or 'pypi'

@dataclass
class EnvInfo:
    name: str
    path: str
    python_version: str
    os_info: str
    platform_machine: str
    packages: Dict[str, PackageDetails] = field(default_factory=dict)
    cuda_driver_version: Optional[str] = None
    gpu_info: List[Dict[str, Any]] = field(default_factory=list)

def get_active_env_info() -> EnvInfo:
    """
    Inspects the current environment and returns a unified EnvInfo object.
    """
    # 1. Basic System Info
    python_version = sys.version.split()[0]
    os_info = f"{platform.system()}-{platform.release()}"
    machine = platform.machine()
    
    # 2. Conda/Env Info
    # Try to get info from conda first
    conda_prefix = sys.prefix
    conda_name = "unknown"
    
    # Heuristic for env name: usually the last part of the prefix
    # But strictly speaking, we might want to check CONDA_DEFAULT_ENV env var
    import os
    if "CONDA_DEFAULT_ENV" in os.environ:
        conda_name = os.environ["CONDA_DEFAULT_ENV"]
    elif "VIRTUAL_ENV" in os.environ:
        conda_name = os.path.basename(os.environ["VIRTUAL_ENV"])
    
    # 3. Packages
    packages = _list_packages()

    # 4. CUDA Driver (Basic check via nvidia-smi if available, or pynvml)
    cuda_version, gpu_details = _detect_cuda_info()

    return EnvInfo(
        name=conda_name,
        path=conda_prefix,
        python_version=python_version,
        os_info=os_info,
        platform_machine=machine,
        packages=packages,
        cuda_driver_version=cuda_version,
        gpu_info=gpu_details
    )

def _list_packages() -> Dict[str, PackageDetails]:
    """
    Lists packages using conda list --json if available, otherwise falls back to pip.
    """
    packages = {}
    
    # Try conda list first
    try:
        result = subprocess.run(
            ["conda", "list", "--json"],
            capture_output=True,
            text=True,
            check=True
        )
        data = json.loads(result.stdout)
        for pkg in data:
            name = pkg.get("name", "").lower()
            version = pkg.get("version", "")
            build = pkg.get("build_string", None)
            channel = pkg.get("channel", None)
            
            # Determine manager
            # Conda output usually has 'channel' like 'pypi' for pip packages
            manager = "conda"
            if channel == "pypi" or pkg.get("scheduler_type") == "pypi":
                manager = "pip"
            
            packages[name] = PackageDetails(
                name=name,
                version=version,
                build=build,
                channel=channel,
                manager=manager
            )
        return packages
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Fallback to pip list --format=json
        pass

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "list", "--format=json"],
            capture_output=True,
            text=True,
            check=True
        )
        data = json.loads(result.stdout)
        for pkg in data:
            name = pkg.get("name", "").lower()
            version = pkg.get("version", "")
            packages[name] = PackageDetails(
                name=name,
                version=version,
                manager="pip"
            )
        return packages
    except Exception:
        # If both fail, return empty (should warn user elsewhere)
        return {}

def _detect_cuda_info() -> tuple[Optional[str], List[Dict[str, Any]]]:
    """
    Attempts to detect the system CUDA driver version and GPU details using pynvml or nvidia-smi.
    """
    driver_version = None
    gpus = []

    # Try pynvml first (v0.2 feature)
    if HAS_PYNVML:
        try:
            pynvml.nvmlInit()
            driver_version = pynvml.nvmlSystemGetDriverVersion()
            device_count = pynvml.nvmlDeviceGetCount()
            for i in range(device_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                name = pynvml.nvmlDeviceGetName(handle)
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                gpus.append({
                    "index": i,
                    "name": name if isinstance(name, str) else name.decode('utf-8'),
                    "total_memory_mb": mem_info.total / 1024 / 1024,
                    "free_memory_mb": mem_info.free / 1024 / 1024
                })
            pynvml.nvmlShutdown()
            return driver_version, gpus
        except Exception:
            pass # Fallback to nvidia-smi

    # Fallback to nvidia-smi
    try:
        # nvidia-smi --query-gpu=driver_version --format=csv,noheader
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            driver_version = result.stdout.strip().split('\n')[0]
    except FileNotFoundError:
        pass
    
    return driver_version, gpus

def list_conda_envs() -> List[Dict[str, str]]:
    envs: List[Dict[str, str]] = []
    try:
        result = subprocess.run(
            ["conda", "env", "list", "--json"],
            capture_output=True,
            text=True,
            check=True
        )
        data = json.loads(result.stdout)
        for path in data.get("envs", []):
            import os
            name = os.path.basename(path)
            envs.append({"name": name, "path": path})
        return envs
    except Exception:
        pass
    try:
        result = subprocess.run(["conda", "env", "list"], capture_output=True, text=True, check=True)
        lines = result.stdout.splitlines()
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                name, path = parts[0], parts[-1]
                envs.append({"name": name, "path": path})
        return envs
    except Exception:
        return envs

def get_env_info_by_name(name: str) -> EnvInfo:
    python_version = sys.version.split()[0]
    os_info = f"{platform.system()}-{platform.release()}"
    machine = platform.machine()
    path = ""
    for e in list_conda_envs():
        if e.get("name") == name:
            path = e.get("path") or ""
            break
    packages: Dict[str, PackageDetails] = {}
    try:
        result = subprocess.run(
            ["conda", "list", "-n", name, "--json"],
            capture_output=True,
            text=True,
            check=True
        )
        data = json.loads(result.stdout)
        for pkg in data:
            pkg_name = pkg.get("name", "").lower()
            version = pkg.get("version", "")
            build = pkg.get("build_string", None)
            channel = pkg.get("channel", None)
            manager = "conda"
            if channel == "pypi" or pkg.get("scheduler_type") == "pypi":
                manager = "pip"
            packages[pkg_name] = PackageDetails(
                name=pkg_name,
                version=version,
                build=build,
                channel=channel,
                manager=manager
            )
    except Exception:
        pass
    try:
        result = subprocess.run(
            ["conda", "run", "-n", name, "python", "-c", "import sys; print(sys.version.split()[0])"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0 and result.stdout:
            python_version = result.stdout.strip().splitlines()[-1]
    except Exception:
        pass
    cuda_version, gpu_details = _detect_cuda_info()
    return EnvInfo(
        name=name,
        path=path,
        python_version=python_version,
        os_info=os_info,
        platform_machine=machine,
        packages=packages,
        cuda_driver_version=cuda_version,
        gpu_info=gpu_details
    )
