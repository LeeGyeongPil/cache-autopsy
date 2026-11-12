"""Shared test helpers: load the bundled practice (mock) samples."""
import json
from pathlib import Path

SAMPLES = Path(__file__).resolve().parent.parent / "src" / "cache_autopsy" / "samples"


def records(name):
    return [json.loads(line) for line in (SAMPLES / name).read_text(encoding="utf-8").splitlines() if line.strip()]


def request(name):
    return json.loads((SAMPLES / "requests" / name).read_text(encoding="utf-8"))


def pin_english_env():
    """Make unittest runs independent of the host language (pytest does this in conftest.py)."""
    import os

    for name in ("CACHE_AUTOPSY_LANG", "LC_ALL", "LC_MESSAGES"):
        os.environ.pop(name, None)
    os.environ["LANG"] = "C"


pin_english_env()  # importing this module pins the environment for unittest-style tests
