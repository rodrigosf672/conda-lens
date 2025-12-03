import json
import time
from pathlib import Path
from typing import Any, Optional

CACHE_DIR = Path.home() / ".conda-lens" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

def cache_path(key: str) -> Path:
    return CACHE_DIR / f"{key}.json"

def read_cache(key: str, max_age: int = 86400) -> Optional[Any]:
    path = cache_path(key)
    if not path.exists():
        return None
    try:
        obj = json.loads(path.read_text())
        if time.time() - float(obj.get("timestamp", 0)) > float(obj.get("expires", max_age)):
            return None
        return obj.get("data")
    except Exception:
        return None

def write_cache(key: str, data: Any, expires: int = 86400) -> None:
    path = cache_path(key)
    obj = {
        "timestamp": time.time(),
        "expires": expires,
        "data": data
    }
    try:
        path.write_text(json.dumps(obj))
    except Exception:
        pass

