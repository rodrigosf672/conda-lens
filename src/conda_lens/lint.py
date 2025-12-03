import ast
import os
from typing import List, Set, Tuple
from .env_inspect import EnvInfo

def get_imports_from_file(file_path: str) -> Set[str]:
    """
    Parses a python file and returns a set of top-level imported package names.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        try:
            tree = ast.parse(f.read(), filename=file_path)
        except SyntaxError:
            return set()

    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                # import numpy.linalg -> numpy
                root = alias.name.split('.')[0]
                imports.add(root)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                # from sklearn.metrics import ... -> sklearn
                root = node.module.split('.')[0]
                imports.add(root)
    return imports

def check_imports(file_path: str, env: EnvInfo) -> List[str]:
    """
    Returns a list of error messages for missing imports.
    """
    used_imports = get_imports_from_file(file_path)
    installed_packages = set(env.packages.keys())
    
    # Mapping from import name to package name (where they differ)
    # This is a huge list in reality, but we'll add common ones.
    # Ideally this should be a data file.
    import_map = {
        "sklearn": "scikit-learn",
        "PIL": "pillow",
        "cv2": "opencv-python", # or opencv-python-headless
        "yaml": "pyyaml",
        "bs4": "beautifulsoup4"
    }
    
    # Reverse check: installed packages might provide the import
    # But checking if 'sklearn' is in 'scikit-learn' is hard without metadata.
    # So we map Import -> Package Name
    
    missing = []
    for imp in used_imports:
        if imp in ["sys", "os", "re", "json", "math", "datetime", "time", "random", "pathlib", "typing", "collections", "itertools", "functools", "abc", "subprocess", "platform", "ast", "dataclasses"]:
            continue # Skip stdlib (incomplete list, but good for MVP)

        pkg_name = import_map.get(imp, imp).lower()
        
        # Simple check: is the package name in the installed list?
        # Note: installed list is all lowercase from env_inspect
        if pkg_name not in installed_packages:
            # Try to be smarter: maybe the import IS the package name (already checked)
            # or maybe it's a known alias.
            
            # Special case for opencv
            if imp == "cv2" and any("opencv" in p for p in installed_packages):
                continue

            missing.append(f"Import '{imp}' not found in environment (expected package '{pkg_name}').")
            
    return missing
