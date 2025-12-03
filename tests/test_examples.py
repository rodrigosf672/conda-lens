import json
import os
import ast
import subprocess
from pathlib import Path


EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"


def test_examples_notebooks_exist_and_reference_conda_lens():
    notebooks_dir = EXAMPLES_DIR / "notebooks"
    assert notebooks_dir.exists(), "examples/notebooks directory is missing"

    expected_files = {
        "data_exploration.ipynb": ["get_active_env_info"],
        "prototyping_experimentation.ipynb": ["MigrationPlanner"],
        "research_process_documentation.ipynb": ["generate_repro_card"],
        "interactive_demo.ipynb": ["conda_lens.magic", "diagnose"],
    }

    for fname, indicators in expected_files.items():
        fpath = notebooks_dir / fname
        assert fpath.exists(), f"Notebook {fname} not found in examples/notebooks"
        # Load as JSON without external deps
        with open(fpath, "r", encoding="utf-8") as f:
            nb = json.load(f)
        # Search code cells for indicator strings
        cells = nb.get("cells", [])
        text = "\n".join(
            "\n".join(cell.get("source", []))
            for cell in cells
            if cell.get("cell_type") == "code"
        )
        for token in indicators:
            assert token in text, f"Notebook {fname} missing reference to {token}"


def test_examples_script_pipeline_runs_and_outputs_summary():
    script = EXAMPLES_DIR / "scripts" / "processing" / "example_pipeline.py"
    assert script.exists(), "example_pipeline.py not found in examples/scripts/processing"

    # Run the script and capture stdout
    proc = subprocess.run(
        ["python", str(script)],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )
    assert proc.returncode == 0, f"example_pipeline.py failed: {proc.stderr}"

    # The script prints a Python dict; parse it safely
    output = proc.stdout.strip().splitlines()[-1] if proc.stdout else "{}"
    try:
        data = ast.literal_eval(output)
    except Exception:
        raise AssertionError(f"Unexpected output format: {output}")

    for key in ["name", "python", "os", "pip", "conda"]:
        assert key in data, f"Missing key '{key}' in example pipeline output"

