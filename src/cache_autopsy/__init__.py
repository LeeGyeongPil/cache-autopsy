"""cache-autopsy: find out why an LLM prompt cache missed, offline.

Public API::

    diff_requests(a, b, provider=None) -> Divergence
    analyze_records(records, pricing=None, session_key=None) -> Report
    lint_request(req, provider=None) -> list[Finding]
"""
from .cost import Pricing
from .diff import diff_requests
from .lint import lint_request
from .model import (CacheAutopsyError, Divergence, Finding, InputFormatError, PairVerdict, Report,
                    UnknownProviderError, Usage)
from .verdict import analyze_records

__version__ = "0.1.1"
__all__ = [
    "diff_requests", "analyze_records", "lint_request", "Pricing",
    "Divergence", "PairVerdict", "Report", "Finding", "Usage",
    "CacheAutopsyError", "InputFormatError", "UnknownProviderError", "__version__",
]
