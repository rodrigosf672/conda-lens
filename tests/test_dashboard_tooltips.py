from unittest.mock import patch
from fastapi.testclient import TestClient
import sys

sys.path.append('src')
import conda_lens.web_ui as web
from conda_lens.env_inspect import EnvInfo, PackageDetails


def make_env(name='test-env'):
    return EnvInfo(
        name=name,
        path=f"/fake/{name}",
        python_version="3.11.0",
        os_info="Darwin-24",
        platform_machine="arm64",
        packages={
            'numpy': PackageDetails(name='numpy', version='1.26.0', manager='conda'),
        },
        cuda_driver_version=None,
        gpu_info=[],
    )


def test_header_buttons_have_tooltips():
    with patch('conda_lens.web_ui.get_active_env_info', return_value=make_env()), \
         patch('conda_lens.web_ui.run_diagnostics', return_value=[]), \
         patch('conda_lens.web_ui.generate_repro_card', return_value={'env': 'test-env'}):
        client = TestClient(web.app)
        r = client.get('/')
        assert r.status_code == 200
        html = r.text
        # Ensure data-tooltip present for all required buttons
        assert 'data-tooltip="Copy environment details to clipboard"' in html
        assert 'data-tooltip="Download environment specification file"' in html
        assert 'data-tooltip="Generate migration plan between environments"' in html
        assert 'data-tooltip="Compare selected environments side-by-side"' in html
        assert 'data-tooltip="Export environment summary as an image"' in html
        # Ensure no duplicate title attributes
        assert 'title="Copy environment details to clipboard"' not in html
        assert 'title="Download environment specification file"' not in html
        assert 'title="Generate migration plan between environments"' not in html
        assert 'title="Compare selected environments side-by-side"' not in html
        assert 'title="Export environment summary as an image"' not in html

def test_package_row_actions_and_accessible_tooltips():
    with patch('conda_lens.web_ui.get_active_env_info', return_value=make_env()), \
         patch('conda_lens.web_ui.run_diagnostics', return_value=[]), \
         patch('conda_lens.web_ui.generate_repro_card', return_value={'env': 'test-env'}):
        client = TestClient(web.app)
        r = client.get('/')
        assert r.status_code == 200
        html = r.text
        assert 'class="row-actions"' in html
        assert 'class="btn-icon-sm"' in html
        assert 'data-tooltip="Copy package name"' in html
        assert 'data-tooltip="Switch package manager"' in html
        assert '[data-tooltip]:focus::after' in html
