import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))  # lets tests import _helpers


@pytest.fixture(autouse=True)
def _english_by_default(monkeypatch):
    """Every test starts in English with a clean language environment, whatever the host uses."""
    from cache_autopsy import i18n

    for name in ("CACHE_AUTOPSY_LANG", "LC_ALL", "LC_MESSAGES"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("LANG", "C")
    i18n.set_lang("en")
    yield
    i18n.set_lang("en")
