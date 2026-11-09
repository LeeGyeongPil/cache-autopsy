"""Shared test helpers: load the bundled practice (mock) samples."""
import json
from pathlib import Path

SAMPLES = Path(__file__).resolve().parent.parent / "src" / "cache_autopsy" / "samples"


def records(name):
    return [json.loads(line) for line in (SAMPLES / name).read_text(encoding="utf-8").splitlines() if line.strip()]


def request(name):
    return json.loads((SAMPLES / "requests" / name).read_text(encoding="utf-8"))
