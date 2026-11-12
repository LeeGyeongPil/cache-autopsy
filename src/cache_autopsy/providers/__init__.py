"""Provider detection by record shape (or by an explicit name)."""
from __future__ import annotations

from ..model import ProviderSpec, UnknownProviderError
from .anthropic import SPEC as ANTHROPIC
from .openai import CHAT as OPENAI_CHAT
from .openai import RESPONSES as OPENAI_RESPONSES

PROVIDERS = {p.name: p for p in (ANTHROPIC, OPENAI_CHAT, OPENAI_RESPONSES)}
ALIASES = {"openai": None, "claude": "anthropic", "chat": "openai_chat", "responses": "openai_responses"}


def get_provider(name: str) -> ProviderSpec:
    key = ALIASES.get(name, name)
    if key is None:  # "openai" alone is ambiguous: decide in detect()
        raise UnknownProviderError.coded("err.provider_ambiguous")
    if key not in PROVIDERS:
        raise UnknownProviderError.coded("err.provider_unknown", name=name, choices=", ".join(PROVIDERS))
    return PROVIDERS[key]


def detect(request: dict, response: dict | None = None, hint: str | None = None) -> ProviderSpec:
    """Pick a provider from an explicit hint, then response shape, then request shape."""
    if hint and hint != "auto":
        return get_provider(hint)
    response = response or {}
    usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
    if "input" in request or "instructions" in request or response.get("object") == "response":
        return OPENAI_RESPONSES
    if "prompt_tokens" in usage or response.get("object") == "chat.completion":
        return OPENAI_CHAT
    if "cache_read_input_tokens" in usage or "cache_creation_input_tokens" in usage or response.get("type") == "message":
        return ANTHROPIC
    if "system" in request:
        return ANTHROPIC
    tools = request.get("tools")
    if isinstance(tools, list) and tools and isinstance(tools[0], dict):
        if "input_schema" in tools[0]:
            return ANTHROPIC
        if "function" in tools[0] or tools[0].get("type") == "function":
            return OPENAI_CHAT
    model = str(request.get("model", ""))
    if model.startswith("claude"):
        return ANTHROPIC
    if model.startswith(("gpt", "o1", "o3", "o4", "chatgpt")):
        return OPENAI_CHAT
    if "response_format" in request or "reasoning_effort" in request or "prompt_cache_key" in request:
        return OPENAI_CHAT
    if "max_tokens" in request and "messages" in request:
        return ANTHROPIC
    raise UnknownProviderError.coded("err.provider_undetected")
