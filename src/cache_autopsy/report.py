"""Text, JSON and Markdown output."""
from __future__ import annotations

import json

from .model import Divergence, Finding, PairVerdict, Report
from .i18n import ljust, rjust, t
from .rules import CAUSES, display_fix


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
    lines = [t("div.reason", value=d.reason), t("div.causes", value=", ".join(d.causes) or "-")]
    where = d.json_path or "-"
    byte = t("div.byte", offset=d.byte_offset) if d.byte_offset is not None else t("div.byte_na")
    lines.append(t("div.where", path=where, byte=byte))
    if not redact and (d.context_before or d.context_after or d.context_prev_after):
        lines.append(t("div.before", value=_esc(d.context_before)))
        lines.append(t("div.old", value=_esc(d.context_prev_after)))
        lines.append(t("div.new", value=_esc(d.context_after)))
    lines.append(t("div.fix", value=display_fix(d.causes, d.reason)))
    return "\n".join(lines)


def analysis_text(report: Report, redact: bool = False) -> str:
    s = report.summary
    out = [t("rep.head", records=s["records"], sessions=s["sessions"], pairs=s["pairs"]), ""]
    for row in report.sessions:
        out.append(t("rep.session", id=row["id"], calls=row["calls"], rate=pct(row["hit_rate"]),
                     tokens=f"{row['missed_tokens']:,}", cost=usd(row["missed_cost_usd"])))
        rows = [p for p in report.pairs if p.session == row["id"]]
        if rows:
            out.append(f"  {'#':>2}  {ljust(t('rep.col_verdict'), 16)} {ljust(t('rep.col_reason'), 48)} "
                       f"{ljust(t('rep.col_path'), 26)} {rjust(t('rep.col_byte'), 6)} "
                       f"{rjust(t('rep.col_tokens'), 11)} {rjust(t('rep.col_usd'), 10)}")
        for p in rows:
            d = p.divergence
            byte = "-" if d.byte_offset is None else str(d.byte_offset)
            out.append(f"  {p.index:>2}  {p.verdict:<16} {_cause_label(p):<48} {(d.json_path or '-'):<26} "
                       f"{byte:>6} {tok(p.missed_tokens, p.tokens_estimated):>11} {usd(p.missed_cost_usd):>10}")
            if p.verdict in ("explained_miss", "unexplained_miss"):
                out.append(t("rep.fix", value=display_fix(p.causes, p.reason)))
                if p.verdict == "unexplained_miss":
                    gap = t("rep.gap_unknown") if p.gap_seconds is None else t("rep.gap", seconds=f"{p.gap_seconds:.0f}")
                    out.append(t("rep.note", gap=gap))
                elif not redact and d.context_after:
                    out.append(t("rep.old", value=_esc(d.context_prev_after[:40])))
                    out.append(t("rep.new", value=_esc(d.context_after[:40])))
            if p.provider_diagnostic:
                out.append(t("rep.provider_says", diagnostic=p.provider_diagnostic, agree=p.agree))
        out.append("")
    out.append(t("rep.total", rate=pct(s["hit_rate"]), tokens=f"{s['missed_tokens']:,}", cost=usd(s["missed_cost_usd"]))
               + (t("rep.estimated") if s["tokens_estimated"] else ""))
    if s["unpriced_models"] and s["missed_cost_usd"] is None:
        out.append(t("rep.cost_unavailable", models=", ".join(s["unpriced_models"])))
    if s["by_cause"]:
        out.append(t("rep.by_cause"))
        for code, row in sorted(s["by_cause"].items(), key=lambda kv: -kv[1]["missed_tokens"]):
            out.append(t("rep.by_cause_row", code=code, pairs=row["pairs"], tokens=f"{row['missed_tokens']:,}",
                         cost=usd(row["missed_cost_usd"])))
    return "\n".join(out)


def analysis_md(report: Report, redact: bool = False) -> str:
    s = report.summary
    out = [t("md.title"), "",
           t("md.summary", rate=pct(s["hit_rate"]), tokens=f"{s['missed_tokens']:,}", cost=usd(s["missed_cost_usd"])), "",
           t("md.pairs_head"),
           "|---|---|---|---|---|---|---|---|"]
    for p in report.pairs:
        d = p.divergence
        out.append(f"| {p.session} | {p.index} | {p.verdict} | {_cause_label(p)} | {d.json_path or '-'} | "
                   f"{'-' if d.byte_offset is None else d.byte_offset} | {tok(p.missed_tokens, p.tokens_estimated)} | {usd(p.missed_cost_usd)} |")
    if s["by_cause"]:
        out += ["", t("md.cause_head"), "|---|---|---|---|"]
        for code, row in sorted(s["by_cause"].items(), key=lambda kv: -kv[1]["missed_tokens"]):
            out.append(f"| {code} | {row['pairs']} | {row['missed_tokens']:,} | {usd(row['missed_cost_usd'])} |")
    return "\n".join(out)


def analysis_json(report: Report, redact: bool = False) -> str:
    return json.dumps(report.to_dict(redact), indent=2, ensure_ascii=False)


def findings_text(findings: list[Finding]) -> str:
    if not findings:
        return t("lint.none")
    out = []
    for f in findings:
        message = t(f.msg_key, **f.msg_params) if f.msg_key else f.message
        fix = t(f"cause.{f.code}.fix") if f.code in CAUSES else f.fix
        out.append(f"{f.severity.upper():<7} {f.code}  path={f.path or '-'}\n        {message}\n        {t('lint.fix_line', value=fix)}")
    warn = sum(f.severity in ("warning", "error") for f in findings)
    out.append(t("lint.summary", warn=warn, info=len(findings) - warn))
    return "\n".join(out)
