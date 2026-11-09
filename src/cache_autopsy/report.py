"""Text, JSON and Markdown output."""
from __future__ import annotations

import json

from .model import Divergence, Finding, PairVerdict, Report
from .rules import fix_for


def pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def usd(value: float | None) -> str:
    return "n/a" if value is None else f"${value:.4f}"


def tok(value: int, estimated: bool) -> str:
    return f"~{value:,}" if estimated else f"{value:,}"


def _cause_label(p: PairVerdict) -> str:
    return "/".join([p.reason, *p.causes]) if p.verdict != "unexplained_miss" else "unexplained/" + ",".join(p.causes)


def _esc(text: str) -> str:
    return text.replace("\n", "\\n")


def divergence_text(d: Divergence, redact: bool = False) -> str:
    lines = [f"reason : {d.reason}", f"causes : {', '.join(d.causes) or '-'}"]
    where = d.json_path or "-"
    byte = f"byte={d.byte_offset}" if d.byte_offset is not None else "byte=n/a (setting change)"
    lines.append(f"where  : path={where} {byte}  (local rendering, see README)")
    if not redact and (d.context_before or d.context_after or d.context_prev_after):
        lines.append(f"before : ...{_esc(d.context_before)}")
        lines.append(f"old    : {_esc(d.context_prev_after)}")
        lines.append(f"new    : {_esc(d.context_after)}")
    lines.append(f"fix    : {d.fix}")
    return "\n".join(lines)


def analysis_text(report: Report, redact: bool = False) -> str:
    s = report.summary
    out = [f"cache-autopsy: {s['records']} calls, {s['sessions']} session(s), {s['pairs']} comparisons", ""]
    for row in report.sessions:
        out.append(f"session {row['id']}: {row['calls']} calls, hit rate {pct(row['hit_rate'])}, "
                   f"missed {row['missed_tokens']:,} tokens, {usd(row['missed_cost_usd'])}")
        rows = [p for p in report.pairs if p.session == row["id"]]
        if rows:
            out.append(f"  {'#':>2}  {'verdict':<16} {'reason / causes':<48} {'path':<26} {'byte':>6} {'missed tok':>11} {'missed usd':>10}")
        for p in rows:
            d = p.divergence
            byte = "-" if d.byte_offset is None else str(d.byte_offset)
            out.append(f"  {p.index:>2}  {p.verdict:<16} {_cause_label(p):<48} {(d.json_path or '-'):<26} "
                       f"{byte:>6} {tok(p.missed_tokens, p.tokens_estimated):>11} {usd(p.missed_cost_usd):>10}")
            if p.verdict in ("explained_miss", "unexplained_miss"):
                fix = fix_for(p.causes, p.reason)
                out.append(f"      fix: {fix}")
                if p.verdict == "unexplained_miss":
                    gap = "unknown gap" if p.gap_seconds is None else f"gap {p.gap_seconds:.0f}s"
                    out.append(f"      note: structure is identical, so this is a suspicion, not a finding ({gap}).")
                elif not redact and d.context_after:
                    out.append(f"      old: ...{_esc(d.context_prev_after[:40])}")
                    out.append(f"      new: ...{_esc(d.context_after[:40])}")
            if p.provider_diagnostic:
                out.append(f"      provider says: {p.provider_diagnostic} (agree={p.agree})")
        out.append("")
    out.append(f"hit rate {pct(s['hit_rate'])} | missed {s['missed_tokens']:,} tokens | missed cost {usd(s['missed_cost_usd'])}"
               + (" | token counts partly estimated (~)" if s["tokens_estimated"] else ""))
    if s["unpriced_models"] and s["missed_cost_usd"] is None:
        out.append(f"cost unavailable: no price for {', '.join(s['unpriced_models'])}; pass --pricing FILE.")
    if s["by_cause"]:
        out.append("by cause:")
        for code, row in sorted(s["by_cause"].items(), key=lambda kv: -kv[1]["missed_tokens"]):
            out.append(f"  {code:<28} {row['pairs']:>3} call(s) {row['missed_tokens']:>9,} tokens {usd(row['missed_cost_usd']):>10}")
    return "\n".join(out)


def analysis_md(report: Report, redact: bool = False) -> str:
    s = report.summary
    out = ["## cache-autopsy report", "",
           f"**Hit rate {pct(s['hit_rate'])}** · missed {s['missed_tokens']:,} tokens · missed cost {usd(s['missed_cost_usd'])}", "",
           "| session | # | verdict | reason / causes | path | byte | missed tokens | missed cost |",
           "|---|---|---|---|---|---|---|---|"]
    for p in report.pairs:
        d = p.divergence
        out.append(f"| {p.session} | {p.index} | {p.verdict} | {_cause_label(p)} | {d.json_path or '-'} | "
                   f"{'-' if d.byte_offset is None else d.byte_offset} | {tok(p.missed_tokens, p.tokens_estimated)} | {usd(p.missed_cost_usd)} |")
    if s["by_cause"]:
        out += ["", "| cause | calls | missed tokens | missed cost |", "|---|---|---|---|"]
        for code, row in sorted(s["by_cause"].items(), key=lambda kv: -kv[1]["missed_tokens"]):
            out.append(f"| {code} | {row['pairs']} | {row['missed_tokens']:,} | {usd(row['missed_cost_usd'])} |")
    return "\n".join(out)


def analysis_json(report: Report, redact: bool = False) -> str:
    return json.dumps(report.to_dict(redact), indent=2, ensure_ascii=False)


def findings_text(findings: list[Finding]) -> str:
    if not findings:
        return "no findings: nothing in this request is likely to break the cache."
    out = []
    for f in findings:
        out.append(f"{f.severity.upper():<7} {f.code}  path={f.path or '-'}\n        {f.message}\n        fix: {f.fix}")
    warn = sum(f.severity in ("warning", "error") for f in findings)
    out.append(f"{warn} warning(s), {len(findings) - warn} info")
    return "\n".join(out)
