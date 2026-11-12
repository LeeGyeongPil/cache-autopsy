"""Pair verdicts (structure + usage) and the session-level analysis."""
from __future__ import annotations

from typing import Iterable

from .cost import Pricing, cacheable_tokens, hit_rate, missed_cost
from .diff import diff_requests
from .model import CacheAutopsyError, Divergence, InputFormatError, PairVerdict, Report, Usage
from .providers import detect
from .records import dotted, parse_ts
from .render import byte_offset, estimate_tokens, render_sections

DEFAULT_MIN_TOKENS = 1024  # provider minimums differ per model (512-4096); override with min_tokens
NO_DIAGNOSIS = {"unavailable", "previous_message_not_found", "comparison_response_not_found"}


def _unexplained_cause(prev_total: int | None, gap: float | None, ttl: int, min_tokens: int) -> str:
    """Best guess for a miss although the structure did not change. Never certain."""
    if prev_total is not None and prev_total < min_tokens:
        return "below_min_tokens"
    if gap is not None and gap > ttl:
        return "ttl_expired_suspected"
    return "provider_side_suspected"


def _estimated_missed(spec, prev_req: dict, div: Divergence) -> int:
    """Without usage: tokens of the previous prompt that sat after the divergence (chars/4)."""
    text, _, _ = render_sections(spec.sections(prev_req))
    total = estimate_tokens(text)
    if div.byte_offset is None:  # a setting changed: assume everything after the tools was lost
        return total
    shared = byte_offset(text, len(text)) and div.byte_offset / byte_offset(text, len(text))
    return total - int(total * min(1.0, shared))


def _judge(spec, prev: dict, cur: dict, ctx: dict) -> PairVerdict:
    prev_req, cur_req = prev["request"], cur["request"]
    div = diff_requests(prev_req, cur_req, provider=spec.name, context=ctx["context"])
    prev_u, cur_u = prev["_usage"], cur["_usage"]
    gap = None
    if prev["_ts"] is not None and cur["_ts"] is not None:
        gap = cur["_ts"] - prev["_ts"]
    reason, causes = div.reason, list(div.causes)
    missed, estimated = 0, False

    if cur_u is not None and prev_u is not None:
        missed = max(0, cacheable_tokens(spec.name, prev_u) - cur_u.cache_read)
    elif not div.prefix_intact:
        missed, estimated = _estimated_missed(spec, prev_req, div), True

    if div.prefix_intact:
        if cur_u is None:
            verdict, missed, estimated = "expected_hit", 0, False
        elif cur_u.cache_read > 0:
            verdict = "hit"
        else:
            verdict = "unexplained_miss"
            reason = "unexplained"
            causes = [_unexplained_cause(prev_u.total_input if prev_u else None, gap,
                                         spec.ttl_seconds(cur_req), ctx["min_tokens"])]
    else:
        verdict = "explained_miss" if (cur_u is None or missed > 0 or cur_u.cache_read == 0) else "hit"

    model = cur_req.get("model") if isinstance(cur_req.get("model"), str) else None
    cost = None
    rates = ctx["pricing"].rates(spec.name, model)
    if rates is not None and missed:
        usage = cur_u or Usage(0, 0)
        cost = missed_cost(rates, missed, usage, spec.ttl_seconds(cur_req) >= 3600)
    elif rates is not None:
        cost = 0.0

    diag = spec.diagnostic(cur.get("response") or {})
    agree: bool | None = None
    if diag is not None and diag not in NO_DIAGNOSIS:
        if diag == "cache_hit":
            agree = verdict in ("hit", "expected_hit")
        else:
            agree = verdict == "explained_miss" and diag == reason

    return PairVerdict(
        session=ctx["session"], index=ctx["index"], verdict=verdict, divergence=div, reason=reason,
        causes=causes, provider=spec.name, model=model, usage=cur_u, prev_usage=prev_u,
        missed_tokens=missed, missed_cost_usd=cost, tokens_estimated=estimated, gap_seconds=gap,
        provider_diagnostic=diag, agree=agree, line=cur.get("_line"))


def analyze_records(records: Iterable[dict], pricing: Pricing | None = None, session_key: str | None = None,
                    provider: str | None = None, min_tokens: int = DEFAULT_MIN_TOKENS,
                    context: int = 40) -> Report:
    """Compare each call with the one before it in the same session and total up the misses.

    ``records`` are dicts like ``{"request": {...}, "response": {...}, "session_id": "s1", "ts": "..."}``.
    """
    pricing = pricing or Pricing.default()
    sessions: dict[str, list[dict]] = {}
    for n, rec in enumerate(records, 1):
        if not isinstance(rec, dict):
            raise InputFormatError.coded("err.record_not_dict", n)
        line = rec.get("_line", n)
        if not isinstance(rec.get("request"), dict):
            raise InputFormatError.coded("err.record_needs_request", line)
        try:
            spec = detect(rec["request"], rec.get("response"), hint=provider)
            rec["_spec"] = spec
            rec["_usage"] = spec.usage(rec["request"], rec.get("response") or {})
            rec["_ts"] = parse_ts(rec.get("ts"))
        except CacheAutopsyError as exc:  # keep the line number so the user can find the bad record
            raise InputFormatError(exc.message, line, exc.code, exc.params) from None
        key = dotted(rec, session_key) if session_key else rec.get("session_id")
        sessions.setdefault(str(key) if key is not None else "default", []).append(rec)

    pairs: list[PairVerdict] = []
    session_rows: list[dict] = []
    all_usages: list[Usage] = []
    for name, recs in sessions.items():
        usages = [r["_usage"] for r in recs if r["_usage"] is not None]
        all_usages.extend(usages)
        start = len(pairs)
        for i in range(1, len(recs)):
            ctx = {"session": name, "index": i, "pricing": pricing, "min_tokens": min_tokens, "context": context}
            pairs.append(_judge(recs[i]["_spec"], recs[i - 1], recs[i], ctx))
        mine = pairs[start:]
        costs = [p.missed_cost_usd for p in mine if p.missed_cost_usd is not None]
        session_rows.append({
            "id": name, "calls": len(recs), "hit_rate": hit_rate(usages),
            "missed_tokens": sum(p.missed_tokens for p in mine),
            "missed_cost_usd": round(sum(costs), 6) if costs else None,
        })

    return Report(summary=_summarise(pairs, all_usages, len(sessions), sum(len(v) for v in sessions.values())),
                  sessions=session_rows, pairs=pairs)


def _summarise(pairs: list[PairVerdict], usages: list[Usage], n_sessions: int, n_records: int) -> dict:
    costs = [p.missed_cost_usd for p in pairs if p.missed_cost_usd is not None]
    by_cause: dict[str, dict] = {}
    for p in pairs:
        if p.verdict not in ("explained_miss", "unexplained_miss"):
            continue
        code = p.causes[0] if p.causes else p.reason
        row = by_cause.setdefault(code, {"pairs": 0, "missed_tokens": 0, "missed_cost_usd": 0.0})
        row["pairs"] += 1
        row["missed_tokens"] += p.missed_tokens
        row["missed_cost_usd"] = round(row["missed_cost_usd"] + (p.missed_cost_usd or 0.0), 6)
    verdicts: dict[str, int] = {}
    for p in pairs:
        verdicts[p.verdict] = verdicts.get(p.verdict, 0) + 1
    return {
        "records": n_records,
        "sessions": n_sessions,
        "pairs": len(pairs),
        "hit_rate": hit_rate(usages),
        "missed_tokens": sum(p.missed_tokens for p in pairs),
        "missed_cost_usd": round(sum(costs), 6) if costs else None,
        "unpriced_models": sorted({p.model or "?" for p in pairs if p.missed_cost_usd is None}),
        "tokens_estimated": any(p.tokens_estimated for p in pairs),
        "verdicts": verdicts,
        "by_cause": by_cause,
    }
