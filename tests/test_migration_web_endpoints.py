from unittest.mock import patch, Mock
from fastapi.testclient import TestClient
import sys

sys.path.append('src')
from conda_lens.web_ui import app
from conda_lens.env_inspect import EnvInfo, PackageDetails
from conda_lens.migration import MigrationReport, MigrationStep, SafetyStatus


def fake_env():
    return EnvInfo(
        name='test-env',
        path='/fake/test-env',
        python_version='3.11.0',
        os_info='Darwin-24',
        platform_machine='arm64',
        packages={
            'numpy': [PackageDetails(name='numpy', version='1.26.0', manager='pip')],
        },
        cuda_driver_version=None,
        gpu_info=[],
    )


import pytest

@pytest.mark.parametrize("target", ["conda", "pip", "uv", "pixi"])
def test_package_plan_endpoint(target):
    step = MigrationStep(
        package_name='numpy', current_manager='pip', current_version='1.26.0',
        target_manager='conda', target_version='1.26.0', safety_status=SafetyStatus.OK,
        reason='Safe to migrate', dependencies=[]
    )
    report = MigrationReport(total_packages=1, safe_to_migrate=1, conflicts=0, unsupported=0, missing=0, steps=[step])
    # Ensure target in report reflects requested manager
    report.steps[0].target_manager = target
    with patch('conda_lens.web_ui.get_active_env_info', return_value=fake_env()), \
         patch('conda_lens.migration.MigrationPlanner.plan_migration', return_value=report):
        client = TestClient(app)
        r = client.get('/api/package-plan', params={'package': 'numpy', 'target': target})
        assert r.status_code == 200
        data = r.json()
        assert data['total_packages'] == 1
        assert data['can_proceed'] is True
        assert data['steps'][0]['package_name'] == 'numpy'
        assert data['steps'][0]['target_manager'] == target


@pytest.mark.parametrize("target", ["conda", "pip", "uv", "pixi"])
def test_migration_execute_dry_run(target):
    step = MigrationStep(
        package_name='numpy', current_manager='pip', current_version='1.26.0',
        target_manager='conda', target_version='1.26.0', safety_status=SafetyStatus.OK,
        reason='Safe to migrate', dependencies=[]
    )
    report = MigrationReport(total_packages=1, safe_to_migrate=1, conflicts=0, unsupported=0, missing=0, steps=[step])
    with patch('conda_lens.web_ui.get_active_env_info', return_value=fake_env()), \
         patch('conda_lens.migration.MigrationPlanner.plan_migration', return_value=report), \
         patch('conda_lens.migration.MigrationPlanner.execute_migration', return_value={'numpy': True}) as mock_exec:
        client = TestClient(app)
        r = client.post('/api/migration-execute', params={'target': target, 'yes': False})
        assert r.status_code == 200
        data = r.json()
        assert data['dry_run'] is True
        assert data['success'] is True
        assert data['success_count'] == 1
        mock_exec.assert_called()
        assert data['failure_count'] == 0

@pytest.mark.parametrize("target", ["conda", "pip", "uv", "pixi"])
def test_migration_execute_failure(target):
    step = MigrationStep(
        package_name='numpy', current_manager='pip', current_version='1.26.0',
        target_manager=target, target_version='1.26.0', safety_status=SafetyStatus.OK,
        reason='Safe to migrate', dependencies=[]
    )
    report = MigrationReport(total_packages=1, safe_to_migrate=1, conflicts=0, unsupported=0, missing=0, steps=[step])
    with patch('conda_lens.web_ui.get_active_env_info', return_value=fake_env()), \
         patch('conda_lens.migration.MigrationPlanner.plan_migration', return_value=report), \
         patch('conda_lens.migration.MigrationPlanner.execute_migration', return_value={'numpy': False}):
        client = TestClient(app)
        r = client.post('/api/migration-execute', params={'target': target, 'yes': True})
        assert r.status_code == 200
        data = r.json()
        assert data['dry_run'] is False
        assert data['success'] is False
        assert data['success_count'] == 0
        assert data['failure_count'] == 1


def test_undo_endpoint():
    with patch('conda_lens.web_ui.get_active_env_info', return_value=fake_env()), \
         patch('conda_lens.migration.MigrationPlanner.undo_last_migration', return_value=True):
        client = TestClient(app)
        r = client.post('/api/undo')
        assert r.status_code == 200
        assert r.json().get('ok') is True
