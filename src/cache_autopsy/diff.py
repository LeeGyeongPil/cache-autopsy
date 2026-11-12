"""First-divergence search and cause classification for two consecutive requests."""
from __future__ import annotations

import json
from typing import Any

from .model import Divergence, InputFormatError, ProviderSpec
from .providers import detect
from .render import byte_offset, dumps, first_diff, locate, render_sections
from .rules import VOLATILE

# Canonical section order across providers; each provider only fills the sections it has.
SECTION_ORDER = ("model", "tools", "system", "instructions", "messages", "input")
HISTORY_SECTIONS = ("messages", "input")  # last sections: appending to them keeps the prefix intact


def _tool_name(tool: Any) -> str:
    if isinstance(tool, dict):
        return str(tool.get("name") or (tool.get("function") or {}).get("name") or dumps(tool))
    return dumps(tool)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _volatile_codes(text_a: str, text_b: str) -> list[str]:
    """Volatile-value kinds whose matches differ between the two texts."""
    found: list[str] = []
    for code, pattern in VOLATILE:
        if code not in found and set(pattern.findall(text_a)) != set(pattern.findall(text_b)):
            found.append(code)
    return found


def _is_append(name: str, va: Any, vb: Any) -> bool:
    if name not in HISTORY_SECTIONS:
        return False
    if isinstance(va, list) and isinstance(vb, list):
        return len(va) <= len(vb) and all(dumps(x) == dumps(y) for x, y in zip(va, vb))
    if isinstance(va, str) and isinstance(vb, str):
        return vb.startswith(va)
    return False


def _classify(name: str, va: Any, vb: Any, ta: str, tb: str, window_a: str, window_b: str) -> list[str]:
    if va is None or vb is None:
        return ["section_added_or_removed"]
    if name == "tools" and isinstance(va, list) and isinstance(vb, list):
        names_a, names_b = [_tool_name(t) for t in va], [_tool_name(t) for t in vb]
        if sorted(names_a) == sorted(names_b) and names_a != names_b and \
                _canonical(sorted(va, key=_tool_name)) == _canonical(sorted(vb, key=_tool_name)):
            return ["tool_order_changed"]
        if _canonical(va) == _canonical(vb):
            return ["json_key_order_changed"]
        return ["tool_definition_changed", *_volatile_codes(ta, tb)]
    if name in ("system", "instructions"):
        return _volatile_codes(ta, tb) or ["system_edited"]
    if name in HISTORY_SECTIONS:
        return ["history_edited", *_volatile_codes(window_a, window_b)]
    return []


def _structural(spec: ProviderSpec, a: dict, b: dict, ctx: int) -> tuple[Divergence | None, str | None]:
    """Earliest section that differs. Returns (divergence, section name)."""
    sa, sb = spec.sections(a), spec.sections(b)
    da, db = dict(sa), dict(sb)
    ra, _, _ = render_sections(sa)
    rb, spans_b, bounds_b = render_sections(sb)
    offset = 0  # equal sections have equal length, so one running offset serves both renderings
    for name in SECTION_ORDER:
        va, vb = da.get(name), db.get(name)
        if name not in da and name not in db:
            continue
        ta = dumps(va) if name in da else ""
        tb = dumps(vb) if name in db else ""
        if name in da and name in db and ta == tb:
            offset += len(ta)
            continue
        inner = first_diff(ta, tb) or 0
        at = offset + inner
        # a new request that is shorter than the old one diverges where it ends: report the section
        path = locate(spans_b, at, name) if at < offset + len(tb) else name
        append = _is_append(name, va, vb)
        if append and isinstance(va, list) and len(vb) > len(va):
            # appended items: point at the first new member instead of the closing bracket
            target = f"{name}[{len(va)}]"
            start = next((sp[0] for sp in spans_b if sp[2] == target), None)
            if start is not None:
                at, path = start, target
        window_a, window_b = ra[max(0, at - ctx): at + 2 * ctx], rb[max(0, at - ctx): at + 2 * ctx]
        causes = ["append_only_ok"] if append else _classify(name, va, vb, ta, tb, window_a, window_b)
        div = Divergence(
            byte_offset=byte_offset(rb, at),
            json_path=path,
            reason=spec.section_reason.get(name, f"{name}_changed"),
            causes=causes,
            context_before=rb[max(0, at - ctx): at],
            context_after=rb[at: at + ctx],
            context_prev_after=ra[at: at + ctx],
            prefix_intact=append,
        )
        return div, name
    return None, None


def _setting_divergence(spec: ProviderSpec, a: dict, b: dict, ctx: int) -> Divergence | None:
    for (reason, label, path, va), (_, _, _, vb) in zip(spec.settings(a), spec.settings(b)):
        if dumps(va) != dumps(vb):
            return Divergence(
                byte_offset=None, json_path=path, reason=reason, causes=[f"setting_changed:{label}"],
                context_before="", context_after=dumps(vb)[:ctx], context_prev_after=dumps(va)[:ctx])
    return None


def diff_requests(a: dict, b: dict, provider: str | None = None, context: int = 40) -> Divergence:
    """Compare two request bodies and report the first point where the cacheable prefix differs.

    ``a`` is the earlier request, ``b`` the later one. Offsets refer to a local rendering of the
    prefix in the provider's documented order, not to the provider's private bytes.
    """
    for label, req in (("first", a), ("second", b)):
        if not isinstance(req, dict):
            raise InputFormatError.coded(f"err.{label}_not_object", type=type(req).__name__)
    spec = detect(b, hint=provider)
    struct, section = _structural(spec, a, b, context)
    setting = _setting_divergence(spec, a, b, context)
    if struct and section == "model":
        return struct
    if setting and spec.settings_first:
        return setting
    if struct and not struct.prefix_intact:
        return struct
    if setting:
        return setting
    if struct:
        return struct
    return Divergence(byte_offset=None, json_path=None, reason="unchanged", causes=["identical"], prefix_intact=True)
