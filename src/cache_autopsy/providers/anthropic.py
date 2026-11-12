"""Anthropic Messages API: prefix order is tools -> system -> messages (docs, checked 2026-11-09)."""
from __future__ import annotations

from typing import Any

from ..model import InputFormatError, ProviderSpec, Usage

# Settings the docs list as invalidating the messages part of the cache.
_SETTINGS = ("tool_choice", "thinking", "output_config")


def sections(req: dict) -> list[tuple[str, Any]]:
    return [(k, req[k]) for k in ("model", "tools", "system", "messages") if req.get(k) is not None]


def settings(req: dict) -> list[tuple[str, str, str, Any]]:
    return [("messages_changed", name, name, req.get(name)) for name in _SETTINGS]


def _int(usage: dict, key: str) -> int:
    value = usage.get(key) or 0
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise InputFormatError.coded("err.usage_int_anthropic", key=key, value=value)
    return value


def usage(req: dict, resp: dict) -> Usage | None:
    u = resp.get("usage")
    if u is None:
        return None
    if not isinstance(u, dict):
        raise InputFormatError.coded("err.usage_not_object")
    # input_tokens only counts tokens AFTER the last cache marker, so the real total is the sum.
    read = _int(u, "cache_read_input_tokens")
    write = _int(u, "cache_creation_input_tokens")
    fresh = _int(u, "input_tokens")
    detail = u.get("cache_creation")
    write_1h = _int(detail, "ephemeral_1h_input_tokens") if isinstance(detail, dict) else 0
    return Usage(total_input=fresh + read + write, cache_read=read, cache_write=write, cache_write_1h=write_1h)


def diagnostic(resp: dict) -> str | None:
    diag = resp.get("diagnostics")
    if not isinstance(diag, dict) or "cache_miss_reason" not in diag:
        return None
    reason = diag["cache_miss_reason"]
    if reason is None:
        return "cache_hit"
    return reason.get("type") if isinstance(reason, dict) else str(reason)


def _marker_ttl(node: Any) -> list[str]:
    found: list[str] = []
    if isinstance(node, dict):
        cc = node.get("cache_control")
        if isinstance(cc, dict) and cc.get("ttl"):
            found.append(str(cc["ttl"]))
        for child in node.values():
            found.extend(_marker_ttl(child))
    elif isinstance(node, list):
        for child in node:
            found.extend(_marker_ttl(child))
    return found


def ttl_seconds(req: dict) -> int:
    return 3600 if "1h" in _marker_ttl(req) else 300


def breakpoints(req: dict) -> list[str]:
    paths: list[str] = []
    if isinstance(req.get("cache_control"), dict):
        paths.append("cache_control")

    def walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            if "cache_control" in node and path:
                paths.append(path)
            for key, child in node.items():
                if key != "cache_control":
                    walk(child, f"{path}.{key}" if path else key)
        elif isinstance(node, list):
            for i, child in enumerate(node):
                walk(child, f"{path}[{i}]")

    for name in ("tools", "system", "messages"):
        if req.get(name) is not None:
            walk(req[name], name)
    return paths


SPEC = ProviderSpec(
    name="anthropic",
    sections=sections,
    section_reason={"model": "model_changed", "tools": "tools_changed", "system": "system_changed",
                    "messages": "messages_changed"},
    settings=settings,
    settings_first=False,
    usage=usage,
    diagnostic=diagnostic,
    ttl_seconds=ttl_seconds,
    breakpoints=breakpoints,
)
