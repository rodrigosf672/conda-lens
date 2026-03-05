
import pytest
from unittest.mock import MagicMock
from conda_lens.env_inspect import EnvInfo, PackageDetails
from conda_lens.rules.version_conflicts import VersionConflictRule
from conda_lens.rules.duplicates import DuplicateRule
from conda_lens.rules.missing_deps import MissingDependencyRule
from conda_lens.rules.python_compat import PythonCompatRule
from conda_lens.rules.abi import ABIRule
from conda_lens.rules.graph import GraphRule
from conda_lens.rules.advanced import EdgeRules

@pytest.fixture
def mock_env():
    return EnvInfo(
        name="test_env",
        path="/test/env",
        python_version="3.10.0",
        os_info="Linux",
        platform_machine="x86_64",
        packages={},
        cuda_driver_version=None,
        gpu_info=[]
    )

def test_version_conflict_basic(mock_env):
    rule = VersionConflictRule()
    
    # Setup: pkg_a requires pkg_b >= 2.0. Installed pkg_b is 1.0.
    pkg_a = PackageDetails(name="pkg_a", version="1.0", depends=["pkg_b >= 2.0"])
    pkg_b = PackageDetails(name="pkg_b", version="1.0")
    
    mock_env.packages = {
        "pkg_a": [pkg_a],
        "pkg_b": [pkg_b]
    }
    
    result = rule.check(mock_env)
    assert result is not None
    assert result.severity == "ERROR"
    assert "requires pkg_b >=2.0" in result.message
    assert "installed: 1.0" in result.message

def test_version_conflict_satisfied(mock_env):
    rule = VersionConflictRule()
    
    # Setup: pkg_a requires pkg_b >= 1.0. Installed pkg_b is 2.0.
    pkg_a = PackageDetails(name="pkg_a", version="1.0", depends=["pkg_b >= 1.0"])
    pkg_b = PackageDetails(name="pkg_b", version="2.0")
    
    mock_env.packages = {
        "pkg_a": [pkg_a],
        "pkg_b": [pkg_b]
    }
    
    result = rule.check(mock_env)
    assert result is None

def test_duplicate_rule(mock_env):
    rule = DuplicateRule()
    
    # Setup: two versions of numpy
    p1 = PackageDetails(name="numpy", version="1.20", manager="conda")
    p2 = PackageDetails(name="numpy", version="1.21", manager="pip")
    
    mock_env.packages = {
        "numpy": [p1, p2]
    }
    
    result = rule.check(mock_env)
    assert result is not None
    assert result.severity == "WARNING"
    assert "numpy: 1.20 (conda), 1.21 (pip)" in result.message

def test_missing_dependency(mock_env):
    rule = MissingDependencyRule()
    
    # Setup: pkg_a requires pkg_c, which is missing
    pkg_a = PackageDetails(name="pkg_a", version="1.0", depends=["pkg_c"])
    
    mock_env.packages = {
        "pkg_a": [pkg_a]
    }
    
    result = rule.check(mock_env)
    assert result is not None
    assert result.severity == "ERROR"
    assert "requires 'pkg_c'" in result.message

def test_python_compat_metadata(mock_env):
    rule = PythonCompatRule()
    mock_env.python_version = "3.9.0"
    
    # Setup: pkg requires python >= 3.10
    pkg = PackageDetails(name="pkg_modern", version="1.0", requires_python=">=3.10")
    
    mock_env.packages = {
        "pkg_modern": [pkg]
    }
    
    result = rule.check(mock_env)
    assert result is not None
    assert "requires Python >=3.10, but current is 3.9.0" in result.message

def test_python_compat_abi_build(mock_env):
    rule = PythonCompatRule()
    mock_env.python_version = "3.10.12"
    
    # Setup: pkg built for py39
    pkg = PackageDetails(name="pkg_wrong", version="1.0", manager="conda", build="py39_0")
    
    mock_env.packages = {
        "pkg_wrong": [pkg]
    }
    
    result = rule.check(mock_env)
    assert result is not None
    assert "targets py39" in result.message
    assert "incompatible with Python 3.10" in result.message

def test_abi_platform_mismatch(mock_env):
    rule = ABIRule()
    mock_env.os_info = "Darwin-21.0.0"
    mock_env.platform_machine = "arm64"
    
    # Setup: osx-64 package on arm64 machine (expected osx-arm64)
    pkg = PackageDetails(name="pkg_wrong_arch", version="1.0", manager="conda", subdir="osx-64")
    
    mock_env.packages = {
        "pkg_wrong_arch": [pkg]
    }
    
    result = rule.check(mock_env)
    assert result is not None
    assert "built for 'osx-64'" in result.message
    assert "environment expects 'osx-arm64'" in result.message

def test_graph_cycle(mock_env):
    rule = GraphRule()
    
    # Setup: A -> B -> A
    pkg_a = PackageDetails(name="pkg_a", version="1.0", depends=["pkg_b"])
    pkg_b = PackageDetails(name="pkg_b", version="1.0", depends=["pkg_a"])
    
    mock_env.packages = {
        "pkg_a": [pkg_a],
        "pkg_b": [pkg_b]
    }
    
    result = rule.check(mock_env)
    assert result is not None
    assert result.severity == "INFO"
    assert "pkg_a -> pkg_b -> pkg_a" in result.message or "pkg_b -> pkg_a -> pkg_b" in result.message
