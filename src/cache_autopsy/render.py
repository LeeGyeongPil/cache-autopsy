"""Deterministic, key-order-preserving serialisation plus offset -> JSON path mapping.

Providers hash the request in their own order; we cannot see the real bytes, so we render
the sections in the documented order with compact JSON (no sort_keys: key order matters).
"""
from __future__ import annotations

import json
from typing import Any

Span = tuple[int, int, str]  # (start char, end char, json path)


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _emit(value: Any, path: str, out: list[str], pos: list[int], spans: list[Span]) -> None:
    """Append compact JSON of ``value`` to ``out`` while recording a span for every member."""
    if isinstance(value, dict):
        out.append("{")
        pos[0] += 1
        for i, (key, child) in enumerate(value.items()):
            if i:
                out.append(",")
                pos[0] += 1
            start = pos[0]
            kjson = dumps(str(key)) + ":"
            out.append(kjson)
            pos[0] += len(kjson)
            child_path = f"{path}.{key}" if path else str(key)
            _emit(child, child_path, out, pos, spans)
            spans.append((start, pos[0], child_path))
        out.append("}")
        pos[0] += 1
    elif isinstance(value, list):
        out.append("[")
        pos[0] += 1
        for i, child in enumerate(value):
            if i:
                out.append(",")
                pos[0] += 1
            start = pos[0]
            child_path = f"{path}[{i}]"
            _emit(child, child_path, out, pos, spans)
            spans.append((start, pos[0], child_path))
        out.append("]")
        pos[0] += 1
    else:
        text = dumps(value)
        out.append(text)
        pos[0] += len(text)


def render_sections(sections: list[tuple[str, Any]]) -> tuple[str, list[Span], dict[str, tuple[int, int]]]:
    """Concatenate sections; return text, member spans and each section's (start, end)."""
    out: list[str] = []
    pos = [0]
    spans: list[Span] = []
    bounds: dict[str, tuple[int, int]] = {}
    for name, value in sections:
        start = pos[0]
        _emit(value, name, out, pos, spans)
        bounds[name] = (start, pos[0])
        spans.append((start, pos[0], name))
    return "".join(out), spans, bounds


def locate(spans: list[Span], offset: int, fallback: str = "") -> str:
    """Deepest JSON path whose span contains ``offset``.

    If the offset sits on a separator (a comma between array items) we report the next
    member, which is the one that actually differs.
    """
    best: Span | None = None
    for span in spans:
        s, e, _ = span
        if s <= offset < e and (best is None or (e - s) < (best[1] - best[0])):
            best = span
    if best is not None:
        return best[2]
    following = [sp for sp in spans if sp[0] > offset]
    if following:
        return min(following, key=lambda sp: (sp[0], -(sp[1] - sp[0])))[2]
    return fallback


def first_diff(a: str, b: str) -> int | None:
    """Index of the first differing character, or None when equal."""
    n = min(len(a), len(b))
    for i in range(n):
        if a[i] != b[i]:
            return i
    return None if len(a) == len(b) else n


def byte_offset(text: str, char_index: int) -> int:
    return len(text[:char_index].encode("utf-8"))


def estimate_tokens(text: str) -> int:
    """Rough token estimate (characters / 4). Always flagged as an estimate by callers."""
    return max(1, len(text) // 4) if text else 0
