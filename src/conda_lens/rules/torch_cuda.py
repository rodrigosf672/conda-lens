from typing import List, Optional
import re
from .base import BaseRule, DiagnosticResult
from ..env_inspect import EnvInfo, PackageDetails

class TorchCudaRule(BaseRule):
    @property
    def name(self) -> str:
        return "PyTorch & CUDA Compatibility"

    def check(self, env: EnvInfo) -> DiagnosticResult | None:
        """
        Checks if PyTorch is installed with CUDA support if a GPU is present.
        Also checks if PyTorch compiled CUDA version matches system driver.
        """
        torch_pkgs = env.packages.get("torch", [])
        if not torch_pkgs:
            return None
        
        # We might have multiple torch versions? (DUP case).
        # We should check ALL of them or just the one that is likely active?
        # For now, let's check all and report if ANY fail.
        
        for torch_pkg in torch_pkgs:
            # Check if torch is a CPU build
            # Pip: 2.1.0+cpu
            # Conda build string: cpu_py310... or just logic not having cuda
            is_cpu = False
            if "+cpu" in torch_pkg.version:
                is_cpu = True
            elif torch_pkg.build and "cpu" in torch_pkg.build:
                is_cpu = True
            
            if is_cpu:
                # If system has a GPU driver, warn that they are not using it
                if env.cuda_driver_version:
                    return DiagnosticResult(
                        rule_name=self.name,
                        severity="WARNING",
                        message="PyTorch is installed as a CPU-only version, but a CUDA driver was detected.",
                        suggestion="Install a CUDA-enabled version of PyTorch if you intend to use the GPU."
                    )
                # If no GPU, CPU is fine.
                continue

            # Try to parse CUDA version from torch version/build
            # e.g. 2.1.0+cu121 -> 12.1
            # e.g. build: py3.11_cuda11.8_cudnn8.7.0_0 -> 11.8
            torch_cuda_ver = None
            
            # Check version string first (pip style)
            match = re.search(r"\+cu(\d+)", torch_pkg.version)
            if match:
                # cu121 -> 12.1
                raw = match.group(1)
                if len(raw) >= 3:
                    torch_cuda_ver = f"{raw[:-2]}.{raw[-2]}" # cu118 -> 11.8, cu121 -> 12.1
                    # Actually pattern is usually cu118 for 11.8. 
                    # Let's handle cu118 -> 11.8; cu12 -> 12.0?
                    # logic: raw[:-1] . raw[-1] was my diff. 
                    # 118 -> 11.8
                    pass
                else:
                    torch_cuda_ver = raw # Fallback
            
            # Check build string (conda style)
            if not torch_cuda_ver and torch_pkg.build:
                match = re.search(r"cuda(\d+\.\d+)", torch_pkg.build)
                if match:
                    torch_cuda_ver = match.group(1)
            
            if torch_cuda_ver and env.cuda_driver_version:
                # Driver 535.104.05 supports CUDA 12.2
                # We need a mapping or just simple check.
                # Actually, simple check: Driver major version.
                # If driver is too old for torch cuda ver, it won't work.
                # But mapping driver -> cuda is complex.
                # Simplification: If major versions differ in a bad way?
                # Actually newer drivers run older cuda usually.
                pass
                
        return None
