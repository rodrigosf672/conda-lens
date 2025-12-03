import os
import json
from pathlib import Path

from conda_lens.cache_utils import write_cache, read_cache, CACHE_DIR


def test_cache_utils_read_write(tmp_path):
    orig = CACHE_DIR
    try:
        # redirect cache dir
        new_dir = tmp_path / "cache"
        new_dir.mkdir()
        globals_dict = __import__("conda_lens.cache_utils", fromlist=["CACHE_DIR"]).__dict__
        globals_dict["CACHE_DIR"] = new_dir

        write_cache("key1", {"a": 1}, expires=2)
        data = read_cache("key1")
        assert data == {"a": 1}
    finally:
        # restore
        __import__("conda_lens.cache_utils", fromlist=["CACHE_DIR"]).__dict__["CACHE_DIR"] = orig

