"""
Tests for package manager migration functionality.
"""

import pytest
import json
import subprocess
from unittest.mock import Mock, patch, MagicMock
from conda_lens.migration import (
    MigrationPlanner,
    MigrationStep,
    MigrationReport,
    SafetyStatus,
    PackageResolver
)
from conda_lens.env_inspect import EnvInfo, PackageDetails


@pytest.fixture
def mock_env():
    """Create a mock environment with test packages."""
    packages = {
        "numpy": [PackageDetails(
            name="numpy",
            version="1.24.0",
            manager="pip",
            build="pypi_0",
            channel="pypi"
        )],
        "pandas": [PackageDetails(
            name="pandas",
            version="2.0.0",
            manager="conda",
            build="py311_0",
            channel="conda-forge"
        )],
        "torch": [PackageDetails(
            name="torch",
            version="2.0.0",
            manager="pip",
            build="cu118",
            channel="pypi"
        )],
    }

    return EnvInfo(
        name="test-env",
        path="/opt/conda/envs/test-env",
        python_version="3.11.0",
        packages=packages,
        os_info="Linux",
        platform_machine="x86_64",
        cuda_driver_version=None,
        gpu_info=[]
    )


class TestPackageResolver:
    """Test package resolution across managers."""
    
    @patch('subprocess.run')
    def test_search_conda_success(self, mock_run):
        """Test successful conda package search."""
        # First call: conda list returns installed package list
        mock_run.side_effect = [
            Mock(returncode=0, stdout='[{"version": "1.24.0"}]')
        ]
        
        version = PackageResolver.search_conda("numpy")
        assert version == "1.24.0"
    
    @patch('subprocess.run')
    def test_search_conda_not_found(self, mock_run):
        """Test conda package not found."""
        # First call: conda list returns empty; second: search returns empty
        mock_run.side_effect = [
            Mock(returncode=0, stdout='[]'),
            Mock(returncode=0, stdout='{}'),
        ]
        
        version = PackageResolver.search_conda("nonexistent")
        assert version is None
    
    @patch('subprocess.run')
    def test_search_pypi_success(self, mock_run):
        """Test successful PyPI package search."""
        # First call (pip show) returns empty; second call (pip index) returns versions
        mock_run.side_effect = [
            Mock(returncode=0, stdout=''),
            Mock(returncode=0, stdout='Available versions: 1.24.0, 1.23.0'),
        ]
        
        version = PackageResolver.search_pypi("numpy")
        assert version == "1.24.0"
    
    @patch('subprocess.run')
    def test_search_timeout(self, mock_run):
        """Test timeout handling."""
        PackageResolver.clear_cache()
        PackageResolver.DISK_CACHE_ENABLED = False
        mock_run.side_effect = subprocess.TimeoutExpired("cmd", 10)
        
        version = PackageResolver.search_conda("numpy")
        assert version is None


class TestMigrationPlanner:
    """Test migration planning logic."""
    
    def test_plan_migration_all_packages(self, mock_env):
        """Test planning migration for all packages."""
        planner = MigrationPlanner(mock_env)
        
        with patch.object(PackageResolver, 'search_conda', return_value="1.24.0"):
            report = planner.plan_migration("conda")
        
        assert report.total_packages >= 2
        assert isinstance(report, MigrationReport)
    
    def test_plan_migration_specific_packages(self, mock_env):
        """Test planning migration for specific packages."""
        planner = MigrationPlanner(mock_env)
        
        with patch.object(PackageResolver, 'search_conda', return_value="1.24.0"):
            report = planner.plan_migration("conda", packages=["numpy"])
        
        assert report.total_packages >= 1
        assert report.steps[0].package_name == "numpy"
    
    def test_analyze_package_missing(self, mock_env):
        """Test analysis when package is missing in target."""
        planner = MigrationPlanner(mock_env)
        pkg = mock_env.packages["numpy"][0]

        with patch.object(PackageResolver, 'search_conda', return_value=None):
            step = planner._analyze_package(pkg, "conda")

        assert step.safety_status == SafetyStatus.MISSING
        assert step.target_version is None

    def test_analyze_package_cuda_risk(self, mock_env):
        """Test CUDA build detection."""
        planner = MigrationPlanner(mock_env)
        pkg = mock_env.packages["torch"][0]

        with patch.object(PackageResolver, 'search_conda', return_value="2.0.0"):
            step = planner._analyze_package(pkg, "conda")

        assert step.safety_status == SafetyStatus.CUDA_RISK

    def test_analyze_package_version_conflict(self, mock_env):
        """Test version mismatch detection."""
        planner = MigrationPlanner(mock_env)
        pkg = mock_env.packages["numpy"][0]

        with patch.object(PackageResolver, 'search_conda', return_value="1.25.0"):
            step = planner._analyze_package(pkg, "conda")

        assert step.safety_status == SafetyStatus.CONFLICT
        assert "1.24.0 → 1.25.0" in step.reason

    def test_analyze_package_safe(self, mock_env):
        """Test safe migration scenario."""
        planner = MigrationPlanner(mock_env)
        pkg = mock_env.packages["numpy"][0]

        with patch.object(PackageResolver, 'search_conda', return_value="1.24.0"):
            step = planner._analyze_package(pkg, "conda")
        
        assert step.safety_status == SafetyStatus.OK
        assert step.is_safe()


class TestMigrationExecution:
    """Test migration execution and rollback."""
    
    def test_execute_migration_dry_run(self, mock_env):
        """Test dry run execution."""
        planner = MigrationPlanner(mock_env)
        
        step = MigrationStep(
            package_name="numpy",
            current_manager="pip",
            current_version="1.24.0",
            target_manager="conda",
            target_version="1.24.0",
            safety_status=SafetyStatus.OK,
            reason="Safe",
            dependencies=[]
        )
        
        report = MigrationReport(
            total_packages=1,
            safe_to_migrate=1,
            conflicts=0,
            unsupported=0,
            missing=0,
            steps=[step]
        )
        
        results = planner.execute_migration(report, dry_run=True)
        assert results["numpy"] is True
    
    @patch('subprocess.run')
    def test_migrate_package_success(self, mock_run, mock_env):
        """Test successful package migration."""
        mock_run.return_value = Mock(returncode=0)
        
        planner = MigrationPlanner(mock_env)
        step = MigrationStep(
            package_name="numpy",
            current_manager="pip",
            current_version="1.24.0",
            target_manager="conda",
            target_version="1.24.0",
            safety_status=SafetyStatus.OK,
            reason="Safe",
            dependencies=[]
        )
        
        success = planner._migrate_package(step)
        assert success is True
        assert mock_run.call_count == 2  # uninstall + install
    
    @patch('subprocess.run')
    def test_migrate_package_failure_rollback(self, mock_run, mock_env):
        """Test rollback on migration failure."""
        # First call (uninstall) succeeds, second (install) fails
        mock_run.side_effect = [
            Mock(returncode=0),  # uninstall success
            subprocess.CalledProcessError(1, "cmd"),  # install failure
            Mock(returncode=0)   # rollback
        ]
        
        planner = MigrationPlanner(mock_env)
        step = MigrationStep(
            package_name="numpy",
            current_manager="pip",
            current_version="1.24.0",
            target_manager="conda",
            target_version="1.24.0",
            safety_status=SafetyStatus.OK,
            reason="Safe",
            dependencies=[]
        )
        
        success = planner._migrate_package(step)
        assert success is False
        assert mock_run.call_count == 3  # uninstall + failed install + rollback

def make_simple_env():
    from conda_lens.env_inspect import EnvInfo, PackageDetails
    return EnvInfo(
        name="simple",
        path="/tmp/simple",
        python_version="3.11.0",
        os_info="Darwin-24",
        platform_machine="arm64",
        packages={
            "a": [PackageDetails(name="a", version="1.0.0", manager="pip")],
            "b": [PackageDetails(name="b", version="1.0.0", manager="pip")],
        },
        cuda_driver_version=None,
        gpu_info=[],
    )

class TestDependencyAwarePlanner:
    def test_blocked_by_dependent_missing_on_target(self):
        env = make_simple_env()
        planner = MigrationPlanner(env)
        def fake_run(cmd, capture_output=True, text=True, timeout=None, check=False):
            if cmd[:2] == ["pip", "show"] and cmd[2] == "b":
                return Mock(returncode=0, stdout="Name: b\nRequires: a\n")
            if cmd[:2] == ["pip", "show"] and cmd[2] == "a":
                return Mock(returncode=0, stdout="Name: a\nRequires:\n")
            if cmd[:2] == ["conda", "search"]:
                return Mock(returncode=0, stdout=json.dumps({cmd[-1]: []}))
            return Mock(returncode=0, stdout="")
        with patch('subprocess.run', side_effect=fake_run), \
             patch.object(PackageResolver, 'search_conda', return_value=None):
            report = planner.plan_migration("conda", packages=["a"])
            assert report.total_packages == 1
            assert report.steps[0].package_name == "a"
            assert report.steps[0].safety_status == SafetyStatus.CONFLICT
            assert "Dependent b" in report.steps[0].reason

    def test_group_migration_toposort(self):
        env = make_simple_env()
        planner = MigrationPlanner(env)
        def fake_run(cmd, capture_output=True, text=True, timeout=None, check=False):
            if cmd[:2] == ["pip", "show"] and cmd[2] == "b":
                return Mock(returncode=0, stdout="Name: b\nRequires: a\n")
            if cmd[:2] == ["pip", "show"] and cmd[2] == "a":
                return Mock(returncode=0, stdout="Name: a\nRequires:\n")
            if cmd[:2] == ["conda", "search"]:
                pkg = cmd[-1]
                return Mock(returncode=0, stdout=json.dumps({pkg: [{"version": "1.0.0", "depends": []}]}))
            return Mock(returncode=0, stdout="")
        with patch('subprocess.run', side_effect=fake_run), \
             patch.object(PackageResolver, 'search_conda', return_value="1.0.0"):
            report = planner.plan_migration("conda", packages=["a"])
            names = [s.package_name for s in report.steps]
            assert set(names) == {"a", "b"}
            assert report.safe_to_migrate == 2 or report.safe_to_migrate == 1
    
    def test_rollback_file_creation(self, mock_env, tmp_path):
        """Test rollback file is created correctly."""
        planner = MigrationPlanner(mock_env)
        planner.rollback_file = tmp_path / "rollback.json"
        
        data = [{
            "package": "numpy",
            "from_manager": "pip",
            "from_version": "1.24.0",
            "to_manager": "conda",
            "to_version": "1.24.0"
        }]
        
        planner._save_rollback(data)
        
        assert planner.rollback_file.exists()
        import json
        with open(planner.rollback_file) as f:
            saved = json.load(f)
        
        assert len(saved) == 1
        assert saved[0]["operations"] == data


class TestMigrationReport:
    """Test migration report functionality."""
    
    def test_can_proceed_safe(self):
        """Test can_proceed with safe migration."""
        report = MigrationReport(
            total_packages=5,
            safe_to_migrate=5,
            conflicts=0,
            unsupported=0,
            missing=0,
            steps=[]
        )
        
        assert report.can_proceed() is True
    
    def test_can_proceed_conflicts(self):
        """Test can_proceed with conflicts."""
        report = MigrationReport(
            total_packages=5,
            safe_to_migrate=3,
            conflicts=2,
            unsupported=0,
            missing=0,
            steps=[]
        )
        
        assert report.can_proceed() is False
    
    def test_can_proceed_missing(self):
        """Test can_proceed with missing packages."""
        report = MigrationReport(
            total_packages=5,
            safe_to_migrate=4,
            conflicts=0,
            unsupported=0,
            missing=1,
            steps=[]
        )
        
        assert report.can_proceed() is False


class TestMigrationStep:
    """Test migration step functionality."""
    
    def test_is_safe_ok(self):
        """Test is_safe with OK status."""
        step = MigrationStep(
            package_name="numpy",
            current_manager="pip",
            current_version="1.24.0",
            target_manager="conda",
            target_version="1.24.0",
            safety_status=SafetyStatus.OK,
            reason="Safe",
            dependencies=[]
        )
        
        assert step.is_safe() is True
    
    def test_is_safe_conflict(self):
        """Test is_safe with conflict status."""
        step = MigrationStep(
            package_name="numpy",
            current_manager="pip",
            current_version="1.24.0",
            target_manager="conda",
            target_version="1.25.0",
            safety_status=SafetyStatus.CONFLICT,
            reason="Version mismatch",
            dependencies=[]
        )
        
        assert step.is_safe() is False
