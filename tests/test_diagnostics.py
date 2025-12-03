import pytest
from conda_lens.env_inspect import EnvInfo, PackageDetails
from conda_lens.rules.torch_cuda import TorchCudaRule
from conda_lens.rules.generic import PipCondaMixRule

def test_torch_cuda_mismatch():
    # Case 1: Torch needs CUDA 12.1, system has 11.8 -> Error
    env = EnvInfo(
        name="test", path="/tmp", python_version="3.11", os_info="linux", platform_machine="x86_64",
        packages={
            "torch": PackageDetails(name="torch", version="2.1.0+cu121", manager="pip")
        },
        cuda_driver_version="11.8"
    )
    rule = TorchCudaRule()
    res = rule.check(env)
    assert res is not None
    assert res.severity == "ERROR"
    assert "built for CUDA 12.1" in res.message

    # Case 2: Torch CPU, system has CUDA -> Warning
    env.packages["torch"] = PackageDetails(name="torch", version="2.0.0+cpu", manager="pip")
    res = rule.check(env)
    assert res is not None
    assert res.severity == "WARNING"
    assert "CPU-only" in res.message

def test_pip_conda_mix():
    env = EnvInfo(
        name="test", path="/tmp", python_version="3.11", os_info="linux", platform_machine="x86_64",
        packages={
            "numpy": PackageDetails(name="numpy", version="1.24.0", manager="pip"),
            "scipy": PackageDetails(name="scipy", version="1.10.0", manager="conda")
        }
    )
    rule = PipCondaMixRule()
    res = rule.check(env)
    assert res is not None
    assert res.severity == "WARNING"
    assert "numpy" in res.message
