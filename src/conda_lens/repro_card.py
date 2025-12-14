import json
import yaml
from dataclasses import asdict
from datetime import datetime
from .env_inspect import EnvInfo, get_active_env_info

def generate_repro_card(env: EnvInfo) -> dict:
    """
    Generates a dictionary representing the reproducibility card.
    """
    card = {
        "meta": {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "tool": "conda-lens"
        },
        "system": {
            "os": env.os_info,
            "arch": env.platform_machine,
            "python": env.python_version,
            "cuda_driver": env.cuda_driver_version
        },
        "environment": {
            "name": env.name,
            "path": env.path
        },
        "packages": []
    }

    # Sort packages by name
    all_pkgs = [p for sublist in env.packages.values() for p in sublist]
    sorted_pkgs = sorted(all_pkgs, key=lambda p: p.name)
    for pkg in sorted_pkgs:
        pkg_dict = {
            "name": pkg.name,
            "version": pkg.version,
            "manager": pkg.manager
        }
        if pkg.build:
            pkg_dict["build"] = pkg.build
        if pkg.channel:
            pkg_dict["channel"] = pkg.channel
        card["packages"].append(pkg_dict)

    return card

def save_repro_card(card: dict, path: str, format: str = "yaml"):
    with open(path, "w") as f:
        if format == "json":
            json.dump(card, f, indent=2)
        else:
            yaml.dump(card, f, sort_keys=False)

def load_card(path: str) -> dict:
    """
    Loads a repro card from a file.
    """
    with open(path, "r") as f:
        if path.endswith(".json"):
            return json.load(f)
        else:
            return yaml.safe_load(f)
