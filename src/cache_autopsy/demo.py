"""`cache-autopsy demo`: run the analyzer on the bundled practice (mock) logs."""
from __future__ import annotations

from importlib import resources

from .cost import Pricing
from .records import read_jsonl
from .report import pct, usd
from .verdict import analyze_records


def samples_dir():
    return resources.files("cache_autopsy").joinpath("samples")


def run_demo() -> int:
    print("NOTE: practice mock data (연습용 목(mock) 데이터). These are NOT real API logs; "
          "usage numbers are invented to follow the providers' rules.")
    print("The analyzer really renders, diffs and classifies the fake requests below.\n")
    pricing = Pricing.default()
    reports = {}
    for label in ("broken", "fixed"):
        path = samples_dir().joinpath(f"anthropic_{label}.jsonl")
        with resources.as_file(path) as real:
            reports[label] = analyze_records(read_jsonl(real), pricing)
    print(f"{'session':<8} {'calls':>5} {'hit rate':>9} {'missed tokens':>14} {'missed cost':>12}")
    for label, rep in reports.items():
        s = rep.summary
        print(f"{label:<8} {s['records']:>5} {pct(s['hit_rate']):>9} {s['missed_tokens']:>14,} {usd(s['missed_cost_usd']):>12}")
    print("\nWhy 'broken' misses (cause: calls, missed tokens):")
    for code, row in sorted(reports["broken"].summary["by_cause"].items(), key=lambda kv: -kv[1]["missed_tokens"]):
        print(f"  {code:<26} {row['pairs']} call(s)  {row['missed_tokens']:,} tokens  {usd(row['missed_cost_usd'])}")
    print("\nTry: cache-autopsy analyze <your-log>.jsonl   |   cache-autopsy causes")
    return 0
