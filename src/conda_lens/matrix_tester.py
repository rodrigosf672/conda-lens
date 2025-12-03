"""
Matrix testing across multiple Python versions.
"""

import subprocess
import sys
import re
from typing import List, Dict, Any


def parse_versions_input(versions: List[str]) -> List[str]:
    """
    Parse and normalize version input.
    
    Handles multiple formats:
    - ["3.10", "3.11", "3.12"] (already parsed)
    - ["3.10,3.11,3.12"] (comma-separated)
    - ["3.10, 3.11, 3.12"] (comma-separated with spaces)
    
    Returns:
        List of normalized version strings
        
    Raises:
        ValueError: If version format is invalid
    """
    if not versions:
        return ["3.10", "3.11"]  # Default versions
    
    normalized = []
    
    for item in versions:
        # Split by comma if present
        parts = [p.strip() for p in item.split(",")]
        normalized.extend(parts)
    
    # Deduplicate while preserving order
    seen = set()
    result = []
    for v in normalized:
        if v and v not in seen:
            # Validate format
            if not re.match(r"^\d+\.\d+$", v):
                raise ValueError(f"Invalid version format: '{v}'. Expected format: X.Y (e.g., 3.10)")
            seen.add(v)
            result.append(v)
    
    return result


def run_matrix_test(python_versions: List[str], test_script: str) -> Dict[str, Dict[str, Any]]:
    """
    Run a smoke test across multiple Python versions using conda environments.
    
    Args:
        python_versions: List of Python versions (e.g., ["3.10", "3.11"])
        test_script: Path to the Python script to test
        
    Returns:
        Dictionary mapping version to test results:
        {
            "3.10": {
                "status": "PASS" | "FAIL" | "SETUP_FAIL",
                "stdout": "...",
                "stderr": "...",
                "exit_code": 0,
                "env_name": "conda-lens-matrix-py310"
            },
            ...
        }
    """
    results = {}
    
    for py_ver in python_versions:
        env_name = f"conda-lens-matrix-py{py_ver.replace('.', '')}"
        
        result_data = {
            "status": "UNKNOWN",
            "stdout": "",
            "stderr": "",
            "exit_code": None,
            "env_name": env_name
        }
        
        try:
            # 1. Create environment
            print(f"Creating environment '{env_name}' with Python {py_ver}...")
            create_proc = subprocess.run(
                ["conda", "create", "-n", env_name, f"python={py_ver}", "-y"],
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout for env creation
            )
            
            if create_proc.returncode != 0:
                result_data["status"] = "SETUP_FAIL"
                result_data["stderr"] = f"Failed to create environment: {create_proc.stderr}"
                result_data["exit_code"] = create_proc.returncode
                results[py_ver] = result_data
                continue
            
            # 2. Run script
            print(f"Running script in Python {py_ver}...")
            run_proc = subprocess.run(
                ["conda", "run", "-n", env_name, "python", test_script],
                capture_output=True,
                text=True,
                timeout=60  # 1 minute timeout for script execution
            )
            
            result_data["stdout"] = run_proc.stdout
            result_data["stderr"] = run_proc.stderr
            result_data["exit_code"] = run_proc.returncode
            
            if run_proc.returncode == 0:
                result_data["status"] = "PASS"
            else:
                result_data["status"] = "FAIL"
                
        except subprocess.TimeoutExpired as e:
            result_data["status"] = "TIMEOUT"
            result_data["stderr"] = f"Command timed out: {str(e)}"
            
        except subprocess.CalledProcessError as e:
            result_data["status"] = "SETUP_FAIL"
            result_data["stderr"] = f"Setup failed: {str(e)}"
            result_data["exit_code"] = e.returncode
            
        except Exception as e:
            result_data["status"] = "ERROR"
            result_data["stderr"] = f"Unexpected error: {str(e)}"
            
        finally:
            # Cleanup: remove environment
            try:
                print(f"Cleaning up environment '{env_name}'...")
                subprocess.run(
                    ["conda", "env", "remove", "-n", env_name, "-y"],
                    capture_output=True,
                    timeout=60
                )
            except Exception:
                pass  # Best effort cleanup
        
        results[py_ver] = result_data
    
    return results
