"""OpenAI Chat Completions and Responses. Tools and the system/instructions/input are part of the prefix."""
from __future__ import annotations

from typing import Any

from ..model import InputFormatError, ProviderSpec, Usage


def _get(obj: Any, *path: str) -> Any:
    for key in path:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(key)
    return obj


def _chat_sections(req: dict) -> list[tuple[str, Any]]:
    return [(k, req[k]) for k in ("model", "tools", "messages") if req.get(k) is not None]


def _resp_sections(req: dict) -> list[tuple[str, Any]]:
    return [(k, req[k]) for k in ("model", "tools", "instructions", "input") if req.get(k) is not None]


def _chat_settings(req: dict) -> list[tuple[str, str, str, Any]]:
    return [
        ("prompt_cache_key_changed", "prompt_cache_key", "prompt_cache_key", req.get("prompt_cache_key")),
        ("service_tier_changed", "service_tier", "service_tier", req.get("service_tier")),
        ("text_format_changed", "response_format", "response_format", req.get("response_format")),
        ("reasoning_effort_changed", "reasoning_effort", "reasoning_effort", req.get("reasoning_effort")),
        ("verbosity_changed", "verbosity", "verbosity", req.get("verbosity")),
    ]


def _resp_settings(req: dict) -> list[tuple[str, str, str, Any]]:
    return [
        ("prompt_cache_key_changed", "prompt_cache_key", "prompt_cache_key", req.get("prompt_cache_key")),
        ("service_tier_changed", "service_tier", "service_tier", req.get("service_tier")),
        ("text_format_changed", "text.format", "text.format", _get(req, "text", "format")),
        ("reasoning_effort_changed", "reasoning.effort", "reasoning.effort", _get(req, "reasoning", "effort")),
        ("verbosity_changed", "text.verbosity", "text.verbosity", _get(req, "text", "verbosity")),
    ]


def _num(value: Any, name: str) -> int:
    if value is None:
        return 0
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise InputFormatError.coded("err.usage_int_openai", name=name, value=value)
    return value


def _usage(resp: dict, total_key: str, details_key: str) -> Usage | None:
    u = resp.get("usage")
    if u is None:
        return None
    if not isinstance(u, dict):
        raise InputFormatError.coded("err.usage_not_object")
    total = _num(u.get(total_key), total_key)
    details = u.get(details_key) if isinstance(u.get(details_key), dict) else {}
    # The cached part is already INSIDE the total here (unlike Anthropic).
    return Usage(total_input=total, cache_read=_num(details.get("cached_tokens"), "cached_tokens"),
                 cache_write=_num(details.get("cache_write_tokens"), "cache_write_tokens"))


def _chat_usage(req: dict, resp: dict) -> Usage | None:
    return _usage(resp, "prompt_tokens", "prompt_tokens_details")


def _resp_usage(req: dict, resp: dict) -> Usage | None:
    return _usage(resp, "input_tokens", "input_tokens_details")


def diagnostic(resp: dict) -> str | None:
    diag = resp.get("prompt_cache_diagnostics")
    if not isinstance(diag, dict):
        return None
    kind = diag.get("type")
    if kind == "cache_miss":
        return diag.get("reason") or "cache_miss"
    return kind


_TTL = {"30m": 1800, "12h": 43200, "24h": 86400}


def ttl_seconds(req: dict) -> int:
    ttl = _get(req, "prompt_cache_options", "ttl") or req.get("prompt_cache_retention")
    return _TTL.get(str(ttl), 600)  # 600 s: assumed in-memory default, see docs/causes.md


def breakpoints(req: dict) -> list[str]:
    return []


_INPUT_REASON = {"model": "model_changed", "tools": "tools_changed", "messages": "input_changed",
                 "instructions": "input_changed", "input": "input_changed"}

CHAT = ProviderSpec("openai_chat", _chat_sections, _INPUT_REASON, _chat_settings, True,
                    _chat_usage, diagnostic, ttl_seconds, breakpoints)
RESPONSES = ProviderSpec("openai_responses", _resp_sections, _INPUT_REASON, _resp_settings, True,
                         _resp_usage, diagnostic, ttl_seconds, breakpoints)
