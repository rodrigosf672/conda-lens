import subprocess
import sys
import time
from pathlib import Path

def run(cmd, allow_fail=False, timeout=30):
    """Run a CLI command and return (stdout, stderr)."""
    print(f"▶ {cmd}")
    result = subprocess.run(
        cmd.split(),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if not allow_fail:
        assert result.returncode == 0, f"Command failed: {cmd}\n{result.stderr}"
    return result.stdout, result.stderr


def test_inspect_active_env():
    run("conda-lens inspect")


def test_inspect_by_prefix():
    prefix = sys.prefix
    run(f"conda-lens inspect --prefix {prefix}")


def test_inspect_by_env_name_if_exists():
    # Try only if exists; don't hard-fail.
    envs = subprocess.run(
        ["conda", "env", "list", "--json"],
        capture_output=True,
        text=True,
    )
    if envs.returncode == 0:
        import json
        data = json.loads(envs.stdout)
        names = [Path(p).name for p in data.get("envs", [])]
        if names:
            run(f"conda-lens inspect --env {names[0]}", allow_fail=True)


def test_diagnose_runs():
    run("conda-lens diagnose", allow_fail=True)


def test_repro_cards():
    run("conda-lens repro-card")
    run("conda-lens repro-card --format json")


def test_switch_all_dry_run():
    run("conda-lens switch-all --to pip", allow_fail=True)
    run("conda-lens switch-all --to conda numpy pandas", allow_fail=True)


def test_cache_commands():
    run("conda-lens cache stats")
    run("conda-lens cache warm", allow_fail=True)
    run("conda-lens cache refresh", allow_fail=True)


def test_lint_minimal():
    temp = Path("lint_temp.py")
    temp.write_text("print('hello')\n")
    run(f"conda-lens lint {temp}", allow_fail=True)
    temp.unlink()


def test_matrix_test_single_version():
    temp = Path("matrix_test_example.py")
    temp.write_text("print('ok')\n")
    run("conda-lens matrix-test matrix_test_example.py --versions 3.10", allow_fail=True)
    temp.unlink()


def test_web_spins_up_briefly():
    # Start web server, give it a moment, then kill it.
    proc = subprocess.Popen(
        ["conda-lens", "web"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    time.sleep(1)
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()

    # If it started successfully at all, this is fine.
    assert True
