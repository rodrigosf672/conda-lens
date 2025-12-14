import json
import platform
import subprocess
import sys
import glob
from pathlib import Path
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
    manager: str = "unknown"  # 'conda' or 'pip'
    depends: List[str] = field(default_factory=list)
    requires_python: Optional[str] = None
    subdir: Optional[str] = None
    location: Optional[str] = None

@dataclass
class EnvInfo:
    name: str
    path: str
    python_version: str
    os_info: str
    platform_machine: str
    # Changed from Dict[str, PackageDetails] to Dict[str, List[PackageDetails]]
    packages: Dict[str, List[PackageDetails]] = field(default_factory=dict)
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
    conda_prefix = sys.prefix
    conda_name = "unknown"
    
    import os
    if "CONDA_DEFAULT_ENV" in os.environ:
        conda_name = os.environ["CONDA_DEFAULT_ENV"]
    elif "VIRTUAL_ENV" in os.environ:
        conda_name = os.path.basename(os.environ["VIRTUAL_ENV"])
    
    # 3. Packages
    packages = _list_packages(Path(conda_prefix))

    # 4. CUDA Driver
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

def _list_packages(prefix: Path) -> Dict[str, List[PackageDetails]]:
    """
    Lists packages by inspecting conda-meta (if available) and running pip inspect.
    Returns a dictionary of package name -> List[PackageDetails] to support duplicates.
    """
    packages: Dict[str, List[PackageDetails]] = {}

    def add_pkg(pkg: PackageDetails):
        if pkg.name not in packages:
            packages[pkg.name] = []
        packages[pkg.name].append(pkg)

    # 1. Conda Packages via conda-meta
    conda_meta_dir = prefix / "conda-meta"
    if conda_meta_dir.exists():
        for json_file in conda_meta_dir.glob("*.json"):
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                name = data.get("name", "").lower()
                if not name:
                    continue
                
                version = data.get("version", "")
                build = data.get("build", "")
                build = data.get("build", "")
                channel = data.get("channel", "")
                subdir = data.get("subdir", "")
                depends = data.get("depends", [])
                
                add_pkg(PackageDetails(
                    name=name,
                    version=version,
                    build=build,
                    channel=channel,
                    subdir=subdir,
                    manager="conda",
                    depends=depends,
                    location=str(prefix / "lib" / "site-packages") # Heuristic for conda
                ))
            except Exception:
                pass


    # 2. Pip Packages via pip inspect
    python_exe = None
    if Path(sys.prefix).resolve() == prefix.resolve():
        python_exe = sys.executable
    else:
        # Simple heuristic to find python
        candidates = [prefix / "bin" / "python", prefix / "python.exe", prefix / "Scripts" / "python.exe"]
        for c in candidates:
            if c.exists():
                python_exe = str(c)
                break
    
    if python_exe:
        try:
            # Run pip inspect
            result = subprocess.run(
                [python_exe, "-m", "pip", "inspect"],
                capture_output=True,
                text=True,
                check=True
            )
            inspect_data = json.loads(result.stdout)
            installed = inspect_data.get("installed", [])
            
            for p in installed:
                metadata = p.get("metadata", {})
                name = metadata.get("name", "").lower() or metadata.get("Name", "").lower()
                version = metadata.get("version", "") or metadata.get("Version", "")
                # Location is usually not in metadata for pip inspect, but we can try derived logic
                # metadata_location is in 'p', not 'metadata' usually?
                # Check top level p for install location?
                # Usually we want site-packages path to detect user-site (~/.local).
                # 'metadata_location' points to .../site-packages/pkg-dist-info
                # So we can parse parent of metadata_location.
                loc = p.get("metadata_location", "")
                if loc:
                     import os
                     location = os.path.dirname(loc)
                else:
                     location = metadata.get("Location", "")

                
                if not name:
                    continue
                
                requires_dist = metadata.get("requires_dist", []) or metadata.get("Requires-Dist", [])
                requires_python = metadata.get("requires_python", None) or metadata.get("Requires-Python", None)
                
                is_duplicate_of_conda = False
                if name in packages:
                    for existing in packages[name]:
                        # If we have a conda package with same version, treat as same installation seen by pip
                        # (Unless user specifically wants to catch shadowing? But usually piped conda pkg shows in pip)
                        if existing.manager == "conda" and existing.version == version:
                            is_duplicate_of_conda = True
                            if requires_python and not existing.requires_python:
                                existing.requires_python = requires_python
                            break
                
                if not is_duplicate_of_conda:
                    add_pkg(PackageDetails(
                        name=name,
                        version=version,
                        manager="pip",
                        depends=requires_dist,
                        requires_python=requires_python,
                        location=location
                    ))
                    
        except Exception:
            pass

    return packages

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
            
    env_path = Path(path) if path else Path(sys.prefix)
    
    packages = {}
    if path:
        packages = _list_packages(env_path)

    # Try to get python version
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
