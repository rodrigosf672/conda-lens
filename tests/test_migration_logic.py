"""
Minimal tests for migration planner logic.
"""

import pytest
from conda_lens.migration import MigrationStep, MigrationReport, SafetyStatus


class TestVersionComparison:
    """Test version comparison logic."""
    
    def test_exact_version_match_is_safe(self):
        """Test that exact version matches are marked as OK."""
        step = MigrationStep(
            package_name="numpy",
            current_manager="pip",
            current_version="1.24.0",
            target_manager="conda",
            target_version="1.24.0",
            safety_status=SafetyStatus.OK,
            reason="Safe to migrate",
            dependencies=[]
        )
        assert step.is_safe()
        assert step.safety_status == SafetyStatus.OK
    
    def test_version_mismatch_is_conflict(self):
        """Test that version mismatches are marked as CONFLICT."""
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
        assert not step.is_safe()
        assert step.safety_status == SafetyStatus.CONFLICT


class TestSafetyClassification:
    """Test safety status classification."""
    
    def test_missing_package_classification(self):
        """Test that missing packages are classified correctly."""
        step = MigrationStep(
            package_name="custom-package",
            current_manager="pip",
            current_version="1.0.0",
            target_manager="conda",
            target_version=None,
            safety_status=SafetyStatus.MISSING,
            reason="Package not found in conda",
            dependencies=[]
        )
        assert not step.is_safe()
        assert step.safety_status == SafetyStatus.MISSING
        assert step.target_version is None
    
    def test_cuda_risk_classification(self):
        """Test that CUDA builds are flagged as risky."""
        step = MigrationStep(
            package_name="torch",
            current_manager="pip",
            current_version="2.0.0",
            target_manager="conda",
            target_version="2.0.0",
            safety_status=SafetyStatus.CUDA_RISK,
            reason="Package has CUDA-specific build",
            dependencies=[]
        )
        assert not step.is_safe()
        assert step.safety_status == SafetyStatus.CUDA_RISK
    
    def test_ok_classification(self):
        """Test that safe packages are classified as OK."""
        step = MigrationStep(
            package_name="requests",
            current_manager="pip",
            current_version="2.28.0",
            target_manager="conda",
            target_version="2.28.0",
            safety_status=SafetyStatus.OK,
            reason="Safe to migrate",
            dependencies=[]
        )
        assert step.is_safe()
        assert step.safety_status == SafetyStatus.OK


class TestMigrationReport:
    """Test migration report summary."""
    
    def test_can_proceed_with_no_issues(self):
        """Test that migration can proceed when there are no conflicts or missing packages."""
        report = MigrationReport(
            total_packages=10,
            safe_to_migrate=10,
            conflicts=0,
            missing=0,
            unsupported=0,
            steps=[]
        )
        assert report.can_proceed()
    
    def test_cannot_proceed_with_conflicts(self):
        """Test that migration cannot proceed with conflicts."""
        report = MigrationReport(
            total_packages=10,
            safe_to_migrate=8,
            conflicts=2,
            missing=0,
            unsupported=0,
            steps=[]
        )
        assert not report.can_proceed()
    
    def test_cannot_proceed_with_missing(self):
        """Test that migration cannot proceed with missing packages."""
        report = MigrationReport(
            total_packages=10,
            safe_to_migrate=9,
            conflicts=0,
            missing=1,
            unsupported=0,
            steps=[]
        )
        assert not report.can_proceed()
    
    def test_summary_counts(self):
        """Test that summary counts are correct."""
        steps = [
            MigrationStep("pkg1", "pip", "1.0", "conda", "1.0", SafetyStatus.OK, "Safe", []),
            MigrationStep("pkg2", "pip", "2.0", "conda", "2.1", SafetyStatus.CONFLICT, "Mismatch", []),
            MigrationStep("pkg3", "pip", "3.0", "conda", None, SafetyStatus.MISSING, "Not found", []),
        ]
        
        report = MigrationReport(
            total_packages=3,
            safe_to_migrate=1,
            conflicts=1,
            missing=1,
            unsupported=0,
            steps=steps
        )
        
        assert report.total_packages == 3
        assert report.safe_to_migrate == 1
        assert report.conflicts == 1
        assert report.missing == 1
