from .base import BaseRule, DiagnosticResult
from ..env_inspect import EnvInfo
import re

class TorchCudaRule(BaseRule):
    @property
    def name(self) -> str:
        return "Torch/CUDA Compatibility"

    def check(self, env: EnvInfo) -> DiagnosticResult | None:
        torch_pkg = env.packages.get("torch")
        if not torch_pkg:
            return None
        
        # Check if torch is a CPU build
        if "cpu" in (torch_pkg.build or "") or "+cpu" in torch_pkg.version:
            # If system has a GPU driver, warn that they are not using it
            if env.cuda_driver_version:
                return DiagnosticResult(
                    rule_name=self.name,
                    severity="WARNING",
                    message="PyTorch is installed as a CPU-only version, but a CUDA driver was detected.",
                    suggestion="Install a CUDA-enabled version of PyTorch if you intend to use the GPU."
                )
            return None

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
                torch_cuda_ver = f"{raw[:-1]}.{raw[-1]}"
            else:
                torch_cuda_ver = raw # Fallback
        
        # Check build string (conda style)
        if not torch_cuda_ver and torch_pkg.build:
            match = re.search(r"cuda(\d+\.\d+)", torch_pkg.build)
            if match:
                torch_cuda_ver = match.group(1)

        if torch_cuda_ver and env.cuda_driver_version:
            # Simple float comparison
            try:
                t_ver = float(torch_cuda_ver)
                s_ver = float(env.cuda_driver_version.split('.')[0] + "." + env.cuda_driver_version.split('.')[1])
                
                # If torch needs a newer CUDA than system has
                # (Note: CUDA is generally backward compatible, but not forward compatible driver-wise)
                # If torch was built with 12.1, it generally needs driver >= 530 (which corresponds to 12.1)
                # But for simplicity, let's just compare major.minor versions.
                # Actually, you can run older CUDA toolkit on newer driver.
                # You CANNOT run newer CUDA toolkit on older driver.
                
                if t_ver > s_ver:
                    return DiagnosticResult(
                        rule_name=self.name,
                        severity="ERROR",
                        message=f"PyTorch built for CUDA {torch_cuda_ver} but system driver is {s_ver}.",
                        suggestion="Upgrade your NVIDIA driver or install an older PyTorch version compatible with your driver."
                    )
            except ValueError:
                pass
        
        return None
