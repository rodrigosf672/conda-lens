"""
Tests for new diagnostic rules: EditableInstallShadowRule, CorruptMetadataRule, ManagerPriorityRule
"""

import pytest
from conda_lens.env_inspect import EnvInfo, PackageDetails
from conda_lens.rules.editable_shadow import EditableInstallShadowRule
from conda_lens.rules.manager_priority import ManagerPriorityRule


@pytest.fixture
def mock_env():
    """Create a basic mock environment for testing."""
    return EnvInfo(
        name="test-env",
        path="/opt/conda/envs/test-env",
        python_version="3.11.0",
        packages={},
        os_info="Linux",
        platform_machine="x86_64",
        cuda_driver_version=None,
        gpu_info=[]
    )


class TestEditableInstallShadowRule:
    """Test editable install shadow detection."""

    def test_detects_editable_shadow(self, mock_env):
        """Should detect when editable install shadows regular install."""
        rule = EditableInstallShadowRule()

        # Setup: same package, one editable, one regular
        mock_env.packages = {
            "mypackage": [
                PackageDetails(
                    name="mypackage",
                    version="1.0.0",
                    manager="pip",
                    location="/home/user/dev/mypackage"  # Editable (dev path)
                ),
                PackageDetails(
                    name="mypackage",
                    version="1.0.0",
                    manager="pip",
                    location="/opt/conda/envs/test-env/lib/python3.11/site-packages"  # Regular
                )
            ]
        }

        result = rule.check(mock_env)
        assert result is not None
        assert result.severity == "WARNING"
        assert "mypackage" in result.message
        assert "editable" in result.message.lower()

    def test_no_issue_when_only_regular_installs(self, mock_env):
        """Should not flag when all installs are regular."""
        rule = EditableInstallShadowRule()

        mock_env.packages = {
            "numpy": [
                PackageDetails(
                    name="numpy",
                    version="1.24.0",
                    manager="pip",
                    location="/opt/conda/envs/test-env/lib/python3.11/site-packages"
                )
            ],
            "pandas": [
                PackageDetails(
                    name="pandas",
                    version="2.0.0",
                    manager="conda",
                    location="/opt/conda/envs/test-env/lib/python3.11/site-packages"
                )
            ]
        }

        result = rule.check(mock_env)
        assert result is None

    def test_no_issue_when_only_editable_install(self, mock_env):
        """Should not flag when only editable install exists."""
        rule = EditableInstallShadowRule()

        mock_env.packages = {
            "mypackage": [
                PackageDetails(
                    name="mypackage",
                    version="1.0.0",
                    manager="pip",
                    location="/home/user/dev/mypackage"
                )
            ]
        }

        result = rule.check(mock_env)
        assert result is None

    def test_detects_multiple_shadows(self, mock_env):
        """Should detect multiple packages with shadow issues."""
        rule = EditableInstallShadowRule()

        mock_env.packages = {
            "package_a": [
                PackageDetails(name="package_a", version="1.0.0", manager="pip",
                             location="/home/user/dev/package_a"),
                PackageDetails(name="package_a", version="1.0.0", manager="pip",
                             location="/opt/conda/lib/site-packages")
            ],
            "package_b": [
                PackageDetails(name="package_b", version="2.0.0", manager="pip",
                             location="/Users/dev/package_b"),
                PackageDetails(name="package_b", version="2.0.0", manager="conda",
                             location="/opt/conda/lib/site-packages")
            ]
        }

        result = rule.check(mock_env)
        assert result is not None
        assert "package_a" in result.message
        assert "package_b" in result.message


class TestManagerPriorityRule:
    """Test multi-manager priority conflict detection."""

    def test_detects_version_mismatch_conflict(self, mock_env):
        """Should flag ERROR when managers have different versions."""
        rule = ManagerPriorityRule()

        mock_env.packages = {
            "numpy": [
                PackageDetails(name="numpy", version="1.24.0", manager="pip"),
                PackageDetails(name="numpy", version="1.26.0", manager="conda")
            ]
        }

        result = rule.check(mock_env)
        assert result is not None
        assert result.severity == "ERROR"
        assert "numpy" in result.message
        assert "version mismatch" in result.message.lower() or "1.24.0" in result.message

    def test_detects_same_version_path_conflict(self, mock_env):
        """Should flag WARNING when managers have same version (path ordering issue)."""
        rule = ManagerPriorityRule()

        mock_env.packages = {
            "pandas": [
                PackageDetails(name="pandas", version="2.0.0", manager="pip"),
                PackageDetails(name="pandas", version="2.0.0", manager="conda")
            ]
        }

        result = rule.check(mock_env)
        assert result is not None
        assert result.severity == "WARNING"
        assert "pandas" in result.message
        assert "path ordering" in result.message.lower() or "2.0.0" in result.message

    def test_no_issue_single_manager(self, mock_env):
        """Should not flag when each package has only one manager."""
        rule = ManagerPriorityRule()

        mock_env.packages = {
            "numpy": [PackageDetails(name="numpy", version="1.24.0", manager="pip")],
            "pandas": [PackageDetails(name="pandas", version="2.0.0", manager="conda")],
            "scipy": [PackageDetails(name="scipy", version="1.11.0", manager="pip")]
        }

        result = rule.check(mock_env)
        assert result is None

    def test_suggests_preferred_manager(self, mock_env):
        """Should suggest conda as preferred manager when present."""
        rule = ManagerPriorityRule()

        mock_env.packages = {
            "torch": [
                PackageDetails(name="torch", version="2.0.0", manager="pip"),
                PackageDetails(name="torch", version="2.1.0", manager="conda")
            ]
        }

        result = rule.check(mock_env)
        assert result is not None
        # Suggestion should mention a manager to keep
        assert "conda" in result.suggestion or "pip" in result.suggestion

    def test_detects_three_way_conflict(self, mock_env):
        """Should detect conflicts with 3+ managers."""
        rule = ManagerPriorityRule()

        mock_env.packages = {
            "requests": [
                PackageDetails(name="requests", version="2.28.0", manager="pip"),
                PackageDetails(name="requests", version="2.31.0", manager="conda"),
                PackageDetails(name="requests", version="2.31.0", manager="uv")
            ]
        }

        result = rule.check(mock_env)
        assert result is not None
        assert result.severity == "ERROR"  # Because versions differ
        assert "requests" in result.message

    def test_handles_multiple_conflicts(self, mock_env):
        """Should handle multiple packages with conflicts."""
        rule = ManagerPriorityRule()

        mock_env.packages = {
            "numpy": [
                PackageDetails(name="numpy", version="1.24.0", manager="pip"),
                PackageDetails(name="numpy", version="1.26.0", manager="conda")
            ],
            "pandas": [
                PackageDetails(name="pandas", version="2.0.0", manager="pip"),
                PackageDetails(name="pandas", version="2.0.0", manager="conda")
            ],
            "scipy": [
                PackageDetails(name="scipy", version="1.11.0", manager="pip"),
                PackageDetails(name="scipy", version="1.12.0", manager="conda")
            ]
        }

        result = rule.check(mock_env)
        assert result is not None
        # Should report multiple conflicts
        assert "numpy" in result.message
        # Should have high-priority conflicts (version mismatches)
        assert "high-priority" in result.message.lower() or "ERROR" in result.severity
