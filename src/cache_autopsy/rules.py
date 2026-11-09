"""Volatile-value patterns and the table of cause codes (description, fix, source)."""
from __future__ import annotations

import re

ISO_TS = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?")
DATE_ONLY = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
EPOCH = re.compile(r"\b1[5-9]\d{8}(?:\d{3})?\b")
UUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)
REQUEST_ID = re.compile(r"\b(?:req|msg|chatcmpl|resp|run|trace)[_-][A-Za-z0-9]{8,}\b")

# (code, compiled pattern) in priority order; first matching kind is reported
VOLATILE = [
    ("timestamp_in_prefix", ISO_TS),
    ("timestamp_in_prefix", DATE_ONLY),
    ("timestamp_in_prefix", EPOCH),
    ("uuid_in_prefix", UUID),
    ("request_id_in_prefix", REQUEST_ID),
]

DOC_ANTHROPIC = "https://platform.claude.com/docs/en/build-with-claude/prompt-caching"
DOC_ANTHROPIC_DIAG = "https://platform.claude.com/docs/en/build-with-claude/cache-diagnostics"
DOC_OPENAI = "https://developers.openai.com/api/docs/guides/prompt-caching"
DOC_OPENAI_DIAG = "https://developers.openai.com/api/docs/guides/prompt-caching/diagnostics"

# code -> (layer, what it means, how to fix, source)
CAUSES: dict[str, tuple[str, str, str, str]] = {
    "model_changed": ("reason", "The model name differs from the previous request.",
                      "Keep one model per cached conversation; caches are per model.", DOC_ANTHROPIC_DIAG),
    "tools_changed": ("reason", "The tool definitions differ; everything after them is invalidated.",
                      "Send the same tool list, in the same order, with identical schemas.", DOC_ANTHROPIC_DIAG),
    "system_changed": ("reason", "The system prompt differs; the system prompt and messages are invalidated.",
                       "Keep the system prompt byte-identical across calls; move changing facts into the last user message.",
                       DOC_ANTHROPIC_DIAG),
    "messages_changed": ("reason", "Something in the message history (or a message-level setting) changed.",
                         "Append new messages only; send earlier turns back exactly as received.", DOC_ANTHROPIC_DIAG),
    "input_changed": ("reason", "The input/messages/instructions differ from the previous request.",
                      "Append only; keep earlier input items and the instructions byte-identical.", DOC_OPENAI_DIAG),
    "prompt_cache_key_changed": ("reason", "prompt_cache_key differs, so the request is routed differently.",
                                 "Use one stable prompt_cache_key per shared prefix.", DOC_OPENAI_DIAG),
    "service_tier_changed": ("reason", "service_tier differs from the previous request.",
                             "Use the same service_tier for requests that should share a cache.", DOC_OPENAI_DIAG),
    "text_format_changed": ("reason", "The structured-output format (response_format / text.format) changed.",
                            "Keep the output schema fixed across the conversation.", DOC_OPENAI_DIAG),
    "reasoning_effort_changed": ("reason", "The reasoning effort changed.",
                                 "Keep reasoning effort constant within a cached conversation.", DOC_OPENAI_DIAG),
    "verbosity_changed": ("reason", "The verbosity setting changed.",
                          "Keep verbosity constant within a cached conversation.", DOC_OPENAI_DIAG),
    "tool_order_changed": ("cause", "Same tools, different order.",
                           "Sort tools (for example by name) before sending, or register them in a fixed order.", DOC_ANTHROPIC_DIAG),
    "json_key_order_changed": ("cause", "Same content, but JSON keys are serialised in a different order.",
                               "Serialise with a deterministic key order (sort_keys=True or one fixed schema builder).", DOC_ANTHROPIC_DIAG),
    "tool_definition_changed": ("cause", "A tool name, description or schema changed.",
                                "Treat tool definitions as versioned constants; change them only on purpose.", DOC_ANTHROPIC_DIAG),
    "timestamp_in_prefix": ("cause", "A date or time value sits inside the cached prefix and changes between calls.",
                            "Move the clock value to the end (last user message) or drop it.", DOC_ANTHROPIC),
    "uuid_in_prefix": ("cause", "A UUID sits inside the cached prefix and changes between calls.",
                       "Remove per-request IDs from system prompt and tool text, or move them to the last message.", DOC_ANTHROPIC),
    "request_id_in_prefix": ("cause", "A per-request ID sits inside the cached prefix.",
                             "Keep request/trace IDs in headers or metadata, not in prompt text.", DOC_ANTHROPIC),
    "history_edited": ("cause", "An earlier message was changed, removed or re-serialised.",
                       "Never rewrite earlier turns; send assistant and tool_result blocks back unchanged.", DOC_ANTHROPIC_DIAG),
    "system_edited": ("cause", "The system prompt text changed.",
                      "Version the system prompt; expect one cache rewrite per deliberate change.", DOC_ANTHROPIC),
    "append_only_ok": ("cause", "The new request only appended messages: the prefix is intact.",
                       "Nothing to fix.", DOC_ANTHROPIC),
    "identical": ("cause", "The two requests render to identical prefixes.", "Nothing to fix.", DOC_ANTHROPIC),
    "section_added_or_removed": ("cause", "A whole section (tools, system, ...) appeared or disappeared.",
                                 "Keep optional sections present in every call of a conversation.", DOC_ANTHROPIC),
    "setting_changed": ("cause", "A cache-relevant request setting changed (shown as setting_changed:<field>).",
                        "Keep tool_choice, thinking and similar settings constant within a conversation.", DOC_ANTHROPIC),
    "below_min_tokens": ("suspected", "The cacheable prefix is probably shorter than the provider minimum, so nothing is cached.",
                         "Make the shared prefix longer than the model minimum (see provider docs) or accept no caching.", DOC_ANTHROPIC),
    "breakpoint_on_volatile_block": ("lint", "A cache marker sits on, or after, a block that changes between calls.",
                                     "Place cache_control on the last stable block, before anything volatile.", DOC_ANTHROPIC),
    "too_many_breakpoints": ("lint", "More than 4 explicit cache_control markers.",
                             "Keep at most 4 explicit markers.", DOC_ANTHROPIC),
    "no_cache_marker": ("lint", "No cache_control marker found in an Anthropic request.",
                        "Add a top-level cache_control or mark the last stable block.", DOC_ANTHROPIC),
    "ttl_expired_suspected": ("suspected", "Structure is identical but the gap to the previous call exceeds the cache lifetime (estimate).",
                              "Call again within the TTL, use the 1-hour TTL, or accept the rewrite.", DOC_ANTHROPIC),
    "provider_side_suspected": ("suspected", "Structure is identical and the gap is short, yet nothing was read. Not provable from the log.",
                                "Check routing hints (prompt_cache_key, request rate), concurrent first calls, and provider status.", DOC_OPENAI),
}


def fix_for(causes: list[str], reason: str) -> str:
    """Best fix text for the most specific cause, falling back to the reason."""
    if any(c.startswith("setting_changed:") for c in causes) and reason in CAUSES and reason != "messages_changed":
        return CAUSES[reason][2]  # e.g. reasoning_effort_changed has its own advice
    for code in causes:
        key = code.split(":", 1)[0]
        if key in CAUSES and key != "append_only_ok":
            return CAUSES[key][2]
    if "append_only_ok" in causes:
        return CAUSES["append_only_ok"][2]
    return CAUSES.get(reason, ("", "", "", ""))[2]


def find_volatile(text: str) -> list[str]:
    """Cause codes for volatile values found in ``text`` (deduplicated, priority order)."""
    found: list[str] = []
    for code, pattern in VOLATILE:
        if pattern.search(text) and code not in found:
            found.append(code)
    return found


def causes_markdown() -> str:
    lines = ["# Cause codes", "",
             "Generated by `cache-autopsy causes --format md`.", "",
             "| Code | Layer | Meaning | How to fix | Source |", "|---|---|---|---|---|"]
    for code, (layer, meaning, fix, src) in CAUSES.items():
        lines.append(f"| `{code}` | {layer} | {meaning} | {fix} | {src} |")
    return "\n".join(lines) + "\n"
