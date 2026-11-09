"""Single-request checks: patterns that will break caching on the next call."""
from __future__ import annotations

import re
from typing import Any

from .model import Finding
from .providers import detect
from .render import estimate_tokens, render_sections
from .rules import CAUSES, find_volatile

MAX_BREAKPOINTS = 4


def _strings(node: Any, path: str):
    """Yield (json path, string) for every string value in ``node``."""
    if isinstance(node, str):
        yield path, node
    elif isinstance(node, dict):
        for key, child in node.items():
            if key != "cache_control":
                yield from _strings(child, f"{path}.{key}" if path else key)
    elif isinstance(node, list):
        for i, child in enumerate(node):
            yield from _strings(child, f"{path}[{i}]")


_ORDER = {"tools": 0, "system": 1, "messages": 2}


def _position(path: str) -> tuple[int, int]:
    """Sort key of a JSON path inside the prefix: (section order, top-level index)."""
    m = re.match(r"(\w+)(?:\[(\d+)\])?", path)
    return (_ORDER.get(m.group(1), 3), int(m.group(2) or 0)) if m else (3, 0)


def lint_request(req: dict, provider: str | None = None, min_tokens: int = 1024) -> list[Finding]:
    """Return findings for one request body. Warnings and errors mean "fix before shipping"."""
    spec = detect(req, hint=provider)
    findings: list[Finding] = []
    prefix_names = [n for n in ("tools", "system", "instructions") if req.get(n) is not None]
    volatile: list[tuple[str, list[str]]] = []  # (path, codes) inside the stable part of the prefix
    for name in prefix_names:
        for path, text in _strings(req[name], name):
            codes = find_volatile(text)
            if codes:
                volatile.append((path, codes))
    # An OpenAI chat prompt keeps its system text inside messages: scan leading system/developer ones.
    for i, msg in enumerate(req.get("messages") or []):
        if isinstance(msg, dict) and msg.get("role") in ("system", "developer"):
            for path, text in _strings(msg.get("content"), f"messages[{i}].content"):
                codes = find_volatile(text)
                if codes:
                    volatile.append((path, codes))
    for path, codes in volatile:
        for code in codes:
            findings.append(Finding(code, "warning", path,
                                    f"a value that changes between calls sits in the cached prefix ({path}).",
                                    CAUSES[code][2]))

    markers = spec.breakpoints(req)
    if spec.name == "anthropic":
        if not markers:
            findings.append(Finding("no_cache_marker", "info", "", "no cache_control marker found; nothing will be cached.",
                                    CAUSES["no_cache_marker"][2]))
        explicit = [m for m in markers if m != "cache_control"]
        if len(markers) > MAX_BREAKPOINTS:
            findings.append(Finding("too_many_breakpoints", "error", markers[MAX_BREAKPOINTS],
                                    f"{len(markers)} cache markers found; the limit is {MAX_BREAKPOINTS}.",
                                    CAUSES["too_many_breakpoints"][2]))
        for m in explicit:
            # a marker caches everything before it: any changing value at or before it breaks the key
            culprit = next((path for path, _ in volatile if _position(path) <= _position(m)), None)
            if culprit:
                findings.append(Finding("breakpoint_on_volatile_block", "warning", m,
                                        f"{m} is cached, but the prefix up to it contains a changing value "
                                        f"({culprit}), so the cache key never repeats.",
                                        CAUSES["breakpoint_on_volatile_block"][2]))

    text, _, _ = render_sections(spec.sections(req))
    if markers or spec.name != "anthropic":
        est = estimate_tokens(text)
        if est < min_tokens:
            findings.append(Finding("below_min_tokens", "info", "",
                                    f"estimated ~{est} tokens (characters/4) is below {min_tokens}; "
                                    "providers skip caching under their per-model minimum.",
                                    CAUSES["below_min_tokens"][2]))
    return findings


def has_problems(findings: list[Finding]) -> bool:
    return any(f.severity in ("warning", "error") for f in findings)
