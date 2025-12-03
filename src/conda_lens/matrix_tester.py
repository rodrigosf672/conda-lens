import subprocess
import sys
from typing import List

def run_matrix_test(python_versions: List[str], test_script: str):
    """
    Runs a smoke test across multiple python versions using conda create.
    """
    results = {}
    
    for py_ver in python_versions:
        env_name = f"conda-lens-test-py{py_ver.replace('.', '')}"
        print(f"Testing on Python {py_ver} (Env: {env_name})...")
        
        try:
            # 1. Create Env
            subprocess.run(
                ["conda", "create", "-n", env_name, f"python={py_ver}", "-y"],
                check=True, capture_output=True
            )
            
            # 2. Run Script (using conda run)
            # Note: This assumes the script doesn't need other deps, or we'd need to install them.
            # For a real tool, we'd accept a requirements.txt too.
            res = subprocess.run(
                ["conda", "run", "-n", env_name, "python", test_script],
                capture_output=True, text=True
            )
            
            if res.returncode == 0:
                results[py_ver] = "PASS"
            else:
                results[py_ver] = f"FAIL: {res.stderr}"
                
        except subprocess.CalledProcessError as e:
            results[py_ver] = f"SETUP FAIL: {str(e)}"
        finally:
            # Cleanup
            subprocess.run(["conda", "env", "remove", "-n", env_name, "-y"], capture_output=True)
            
    return results
