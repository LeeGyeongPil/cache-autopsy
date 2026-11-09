"""Regenerate the bundled practice (mock) logs. Deterministic: no clock, no randomness, no network.

    python scripts/make_samples.py            # writes src/cache_autopsy/samples/

Everything here is FAKE data about an imaginary bookstore. The request bodies are realistic in
shape; the usage numbers are invented to follow each provider's accounting rules.
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "src/cache_autopsy/samples"
(OUT / "requests").mkdir(parents=True, exist_ok=True)
T0 = datetime(2026, 11, 9, 10, 0, 0, tzinfo=timezone.utc)


def stamp(seconds):
    return (T0 + timedelta(seconds=seconds)).isoformat()


def write_jsonl(name, rows):
    with (OUT / name).open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_json(name, obj):
    (OUT / "requests" / name).write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


POLICY = "\n".join(
    f"Policy {i}: Answer politely, cite the order id, never invent stock levels, and keep replies under 120 words."
    for i in range(1, 121))
STATIC = "You are a support assistant for a fictional bookstore. Follow the policy below exactly.\n" + POLICY
NOW = "Current time: 2026-11-09T10:05:31Z\n"


def tool(name, desc, prop, keys_first="type"):
    props, required = {prop: {"type": "string"}}, [prop]
    schema = {"type": "object", "properties": props, "required": required}
    if keys_first == "required":  # same content, different key order
        schema = {"required": required, "properties": props, "type": "object"}
    return {"name": name, "description": desc, "input_schema": schema}


def search(k="type"):
    return tool("search_orders", "Search orders by customer email", "email", k)


def stock(k="type"):
    return tool("get_stock", "Get stock level for a book id", "book_id", k)


TURNS = [
    "Where is my order 1042?", "Let me check order 1042 for you.",
    "Also, is 'Dune' in stock?", "Checking stock for Dune.",
    "Thanks. Can I change the address?", "Yes, tell me the new address.",
    "12 Example Street.", "Updated.",
    "Great, bye.", "Goodbye! Anything else?",
    "Actually, one more thing.", "Sure, go ahead.",
    "Do you gift wrap?", "Yes, for a small fee.",
    "Please wrap it.", "Done.", "Thank you!",
]


def messages(n, stamped=False):
    out = []
    for i, text in enumerate(TURNS[:n]):
        role = "user" if i % 2 == 0 else "assistant"
        if stamped and role == "user":  # the clock lives in the user turn, never in the prefix
            text = f"[{(T0 + timedelta(seconds=60 * i)).strftime('%H:%M:%S')}] {text}"
        out.append({"role": role, "content": text})
    return out


def anthropic_req(n, tools, system, tool_choice=None, stamped=False):
    req = {"model": "claude-sonnet-4-5", "max_tokens": 512, "cache_control": {"type": "ephemeral"},
           "tools": tools, "system": system, "messages": messages(n, stamped)}
    if tool_choice:
        req["tool_choice"] = tool_choice
    return req


def a_usage(fresh, write, read):
    return {"input_tokens": fresh, "cache_creation_input_tokens": write, "cache_read_input_tokens": read,
            "output_tokens": 20}


def a_row(i, sid, seconds, req, usage):
    return {"session_id": sid, "provider": "anthropic", "ts": stamp(seconds), "request": req,
            "response": {"id": f"msg_mock_{sid}_{i}", "type": "message", "usage": usage}}


# --- broken session: five calls with the classic mistakes, then three "mystery" misses -------------
T = [search(), stock()]
T_SWAPPED = [stock(), search()]
T_KEYS = [stock("required"), search("required")]
broken_calls = [
    (anthropic_req(1, T, STATIC), a_usage(12, 3410, 0), 0),                       # first call: cache write
    (anthropic_req(3, T, STATIC), a_usage(14, 30, 3410), 60),                    # appended only: hit
    (anthropic_req(5, T_SWAPPED, STATIC), a_usage(15, 3470, 0), 120),            # tool order changed
    (anthropic_req(7, T_SWAPPED, NOW + STATIC), a_usage(13, 3520, 0), 180),      # clock in system prompt
    (anthropic_req(9, T_KEYS, NOW + STATIC), a_usage(11, 3560, 0), 240),         # schema key order changed
    (anthropic_req(9, T_KEYS, NOW + STATIC), a_usage(11, 3560, 0), 660),         # identical, 7 min later
    (anthropic_req(9, T_KEYS, NOW + STATIC), a_usage(11, 3560, 0), 690),         # identical, 30 s later
    (anthropic_req(9, T_KEYS, NOW + STATIC, {"type": "any"}), a_usage(11, 3560, 0), 720),  # tool_choice added
]
write_jsonl("anthropic_broken.jsonl", [a_row(i, "broken", s, r, u) for i, (r, u, s) in enumerate(broken_calls)])

# --- fixed session: same conversation, tools sorted, keys fixed, clock moved to the user turn --------
FIXED_TOOLS = [stock(), search()]  # sorted by name; schema keys in one fixed order
fixed_rows, previous = [], 0
for i, n in enumerate(range(1, 16, 2)):
    req = anthropic_req(n, FIXED_TOOLS, STATIC, stamped=True)
    total = len(json.dumps(req, separators=(",", ":"), ensure_ascii=False)) // 4
    read = previous
    write = total - read - 12
    fixed_rows.append(a_row(i, "fixed", 30 * i, req, a_usage(12, write, read)))
    previous = total
write_jsonl("anthropic_fixed.jsonl", fixed_rows)

# --- OpenAI Chat Completions: cached_tokens is part of prompt_tokens, counted in 128 steps ---------
SYS_CHAT = {"role": "system", "content": STATIC}


def chat_req(n, effort="low", fmt=None, key="bookstore-v1"):
    req = {"model": "gpt-5.4", "prompt_cache_key": key, "reasoning_effort": effort,
           "messages": [SYS_CHAT, *messages(n)]}
    if fmt:
        req["response_format"] = fmt
    return req


FMT = {"type": "json_schema", "json_schema": {"name": "reply", "strict": True,
                                              "schema": {"type": "object", "properties": {"text": {"type": "string"}},
                                                         "required": ["text"], "additionalProperties": False}}}


def chat_row(i, seconds, req, prompt, cached, diag=None):
    resp = {"id": f"chatcmpl-mock{i:04d}xxxx", "object": "chat.completion",
            "usage": {"prompt_tokens": prompt, "completion_tokens": 20, "total_tokens": prompt + 20,
                      "prompt_tokens_details": {"cached_tokens": cached}}}
    if diag:
        resp["prompt_cache_diagnostics"] = diag
    return {"session_id": "chat", "ts": stamp(seconds), "request": req, "response": resp}


write_jsonl("openai_chat.jsonl", [
    chat_row(0, 0, chat_req(1), 3400, 0),
    chat_row(1, 20, chat_req(3), 3450, 3328),                                     # appended: hit
    chat_row(2, 40, chat_req(5, effort="high"), 3500, 0),                          # reasoning effort changed
    chat_row(3, 60, chat_req(7, effort="high", fmt=FMT), 3600, 0,
             {"type": "cache_miss", "reason": "text_format_changed"}),             # response_format added
    chat_row(4, 80, chat_req(9, effort="high", fmt=FMT), 3650, 3584),              # stable again: hit
])


# --- OpenAI Responses: input items, text.format, reasoning.effort -----------------------------------
def resp_req(n, effort="low", fmt=None):
    req = {"model": "gpt-5.4", "prompt_cache_key": "bookstore-v1", "instructions": STATIC,
           "reasoning": {"effort": effort}, "input": messages(n)}
    if fmt:
        req["text"] = {"format": fmt}
    return req


def resp_row(i, seconds, req, tokens, cached):
    return {"session_id": "responses", "ts": stamp(seconds), "request": req,
            "response": {"id": f"resp_mock{i:04d}xxxx", "object": "response",
                         "usage": {"input_tokens": tokens, "output_tokens": 20,
                                   "input_tokens_details": {"cached_tokens": cached}}}}


FMT_RESP = {"type": "json_schema", "name": "reply", "strict": True, "schema": FMT["json_schema"]["schema"]}
write_jsonl("openai_responses.jsonl", [
    resp_row(0, 0, resp_req(1), 3400, 0),
    resp_row(1, 20, resp_req(3), 3450, 3328),
    resp_row(2, 40, resp_req(5, effort="medium"), 3500, 0),
    resp_row(3, 60, resp_req(7, effort="medium", fmt=FMT_RESP), 3550, 0),
])

# --- single request bodies for `diff` and `lint` -----------------------------------------------------
write_json("tools_a.json", anthropic_req(1, T, STATIC))
write_json("tools_b.json", anthropic_req(1, T_SWAPPED, STATIC))
marker = {"type": "ephemeral"}
write_json("volatile_system.json", {
    "model": "claude-sonnet-4-5", "max_tokens": 512, "tools": T,
    "system": [{"type": "text", "text": NOW + STATIC, "cache_control": marker}],
    "messages": messages(1)})
write_json("clean.json", {
    "model": "claude-sonnet-4-5", "max_tokens": 512, "tools": FIXED_TOOLS,
    "system": [{"type": "text", "text": STATIC, "cache_control": marker}],
    "messages": messages(1, stamped=True)})
print(f"wrote practice (mock) samples to {OUT}")
