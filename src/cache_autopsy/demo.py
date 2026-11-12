"""`cache-autopsy demo`: run the analyzer on the bundled practice (mock) logs."""
from __future__ import annotations

from importlib import resources

from .cost import Pricing
from .i18n import ljust, rjust, t
from .records import read_jsonl
from .report import pct, usd
from .verdict import analyze_records


def samples_dir():
    return resources.files("cache_autopsy").joinpath("samples")


def run_demo() -> int:
    print(t("demo.note"))
    print(t("demo.note2") + "\n")
    pricing = Pricing.default()
    reports = {}
    for label in ("broken", "fixed"):
        path = samples_dir().joinpath(f"anthropic_{label}.jsonl")
        with resources.as_file(path) as real:
            reports[label] = analyze_records(read_jsonl(real), pricing)
    print(f"{ljust(t('demo.col_session'), 8)} {rjust(t('demo.col_calls'), 5)} {rjust(t('demo.col_rate'), 9)} "
          f"{rjust(t('demo.col_tokens'), 14)} {rjust(t('demo.col_cost'), 12)}")
    for label, rep in reports.items():
        s = rep.summary
        print(f"{label:<8} {s['records']:>5} {pct(s['hit_rate']):>9} {s['missed_tokens']:>14,} {usd(s['missed_cost_usd']):>12}")
    print("\n" + t("demo.why"))
    for code, row in sorted(reports["broken"].summary["by_cause"].items(), key=lambda kv: -kv[1]["missed_tokens"]):
        print(t("demo.row", code=code, pairs=row["pairs"], tokens=f"{row['missed_tokens']:,}", cost=usd(row["missed_cost_usd"])))
    print("\n" + t("demo.try"))
    return 0
