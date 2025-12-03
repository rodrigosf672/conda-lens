import json
from unittest.mock import patch

from fastapi.testclient import TestClient

import sys
from pathlib import Path
sys.path.append('src')
from conda_lens.web_ui import app, _prefs_path
from conda_lens.env_inspect import EnvInfo, PackageDetails


def test_preferences_persist(tmp_path, monkeypatch):
    monkeypatch.setenv('HOME', str(tmp_path))
    client = TestClient(app)

    # Initially no preference
    r = client.get('/api/preferences/last-env')
    assert r.status_code == 200
    assert r.json().get('name') is None

    # Set preference
    r = client.post('/api/preferences/last-env', params={'name': 'myenv'})
    assert r.status_code == 200
    assert r.json().get('ok') is True

    # Verify persisted to file
    prefs_path = _prefs_path()
    assert prefs_path.exists()
    data = json.loads(prefs_path.read_text())
    assert data.get('last_env') == 'myenv'

    # New client still reads preference
    client2 = TestClient(app)
    r2 = client2.get('/api/preferences/last-env')
    assert r2.status_code == 200
    assert r2.json().get('name') == 'myenv'


def make_env(name, pkgs):
    return EnvInfo(
        name=name,
        path=f"/fake/{name}",
        python_version="3.11.0",
        os_info="Darwin-24",
        platform_machine="arm64",
        packages={k: PackageDetails(name=k, version=v, manager="conda") for k, v in pkgs.items()},
        cuda_driver_version=None,
        gpu_info=[],
    )


def test_compare_endpoint_diff():
    a = make_env('A', {'numpy': '1.26.0', 'pandas': '2.1.0'})
    b = make_env('B', {'numpy': '1.26.1', 'scipy': '1.11.3'})

    with patch('conda_lens.web_ui.get_env_info_by_name', side_effect=lambda n: a if n=='A' else b):
        client = TestClient(app)
        r = client.get('/api/compare', params={'envA': 'A', 'envB': 'B'})
        assert r.status_code == 200
        data = r.json()
        assert data['envA'] == 'A'
        assert data['envB'] == 'B'
        # numpy mismatch
        mismatches = {m['name']: (m['a_version'], m['b_version']) for m in data['version_mismatches']}
        assert mismatches.get('numpy') == ('1.26.0', '1.26.1')
        # pandas only in A
        assert 'pandas' in data['only_in_a']
        # scipy only in B
        assert 'scipy' in data['only_in_b']
