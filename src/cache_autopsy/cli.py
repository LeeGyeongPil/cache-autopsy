"""Command line entry point. Exit codes: 0 ok, 1 gate failed, 2 input error."""
from __future__ import annotations

import argparse
import sys

from . import __version__
from .cost import Pricing
from .diff import diff_requests
from .lint import has_problems, lint_request
from .model import CacheAutopsyError
from .records import read_jsonl, read_request
from .report import analysis_json, analysis_md, analysis_text, divergence_text, findings_text
from .rules import CAUSES, causes_markdown
from .verdict import DEFAULT_MIN_TOKENS, analyze_records

PROVIDER_CHOICES = ["auto", "anthropic", "openai_chat", "openai_responses"]


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="cache-autopsy",
                                description="Find out why an LLM prompt cache missed (offline, no network).")
    p.add_argument("--version", action="version", version=f"cache-autopsy {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp, fmt=True):
        sp.add_argument("--provider", choices=PROVIDER_CHOICES, default="auto", help="force the provider (default: detect)")
        sp.add_argument("--context", type=int, default=40, help="characters of context to show (default 40)")
        sp.add_argument("--redact", action="store_true", help="do not print any request text")
        if fmt:
            sp.add_argument("--format", choices=["text", "json", "md"], default="text")

    d = sub.add_parser("diff", help="first divergence between two request bodies")
    d.add_argument("a"), d.add_argument("b")
    common(d)

    a = sub.add_parser("analyze", help="hit rate, missed cost and causes for a JSONL call log")
    a.add_argument("log")
    common(a)
    a.add_argument("--pricing", help="JSON file overriding the bundled prices")
    a.add_argument("--session-key", help="dotted path to group calls, e.g. request.metadata.user_id")
    a.add_argument("--min-tokens", type=int, default=DEFAULT_MIN_TOKENS, help="provider minimum cacheable tokens")
    a.add_argument("--fail-under", type=float, help="exit 1 if the overall hit rate is below this (0-1)")
    a.add_argument("--fail-on", help="comma list of verdicts or cause codes that make the run fail")

    l = sub.add_parser("lint", help="risky patterns in one request body")
    l.add_argument("request")
    common(l, fmt=False)
    l.add_argument("--min-tokens", type=int, default=DEFAULT_MIN_TOKENS)

    c = sub.add_parser("causes", help="list cause codes and how to fix them")
    c.add_argument("--format", choices=["text", "md"], default="text")

    sub.add_parser("demo", help="run the bundled practice (mock) data, no keys needed")
    return p


def _provider(args) -> str | None:
    return None if args.provider == "auto" else args.provider


VERDICTS = {"hit", "expected_hit", "explained_miss", "unexplained_miss", "unexplained"}


def _check_gate_options(args) -> set[str]:
    """Validate --fail-under / --fail-on before any work so a typo cannot silently disable the gate."""
    if args.fail_under is not None and not 0 <= args.fail_under <= 1:
        raise CacheAutopsyError(f"--fail-under must be a ratio between 0 and 1 (got {args.fail_under}). "
                                "Write 0.6 for 60%.")
    wanted = {w.strip() for w in (args.fail_on or "").split(",") if w.strip()}
    unknown = sorted(wanted - set(CAUSES) - VERDICTS)
    if unknown:
        raise CacheAutopsyError(f"unknown --fail-on value(s): {', '.join(unknown)}. "
                                "Run `cache-autopsy causes` for cause codes; verdicts are "
                                + ", ".join(sorted(VERDICTS)) + ".")
    return wanted


def _run(args) -> int:
    if args.cmd == "diff":
        div = diff_requests(read_request(args.a), read_request(args.b), _provider(args), args.context)
        if args.format == "json":
            import json
            print(json.dumps(div.to_dict(), indent=2, ensure_ascii=False))
        else:
            print(divergence_text(div, args.redact))
        return 0

    if args.cmd == "analyze":
        wanted = _check_gate_options(args)
        pricing = Pricing.from_file(args.pricing) if args.pricing else Pricing.default()
        report = analyze_records(read_jsonl(args.log), pricing, args.session_key, _provider(args),
                                 args.min_tokens, args.context)
        if report.summary["records"] == 0:
            print(f"warning: no records in {args.log}.", file=sys.stderr)
        render = {"text": analysis_text, "json": analysis_json, "md": analysis_md}[args.format]
        print(render(report, args.redact))
        failed = False
        rate = report.summary["hit_rate"]
        if args.fail_under is not None:
            if rate is None:
                print("cannot apply --fail-under: the log has no usage data.", file=sys.stderr)
                return 2
            if rate < args.fail_under:
                print(f"FAIL: hit rate {rate:.2f} < {args.fail_under:.2f}", file=sys.stderr)
                failed = True
        if args.fail_on:
            hits = [p for p in report.pairs if p.verdict in wanted or wanted & set(p.causes) or p.reason in wanted]
            if hits:
                print(f"FAIL: {len(hits)} comparison(s) match --fail-on {args.fail_on}", file=sys.stderr)
                failed = True
        return 1 if failed else 0

    if args.cmd == "lint":
        findings = lint_request(read_request(args.request), _provider(args), args.min_tokens)
        print(findings_text(findings))
        return 1 if has_problems(findings) else 0

    if args.cmd == "causes":
        if args.format == "md":
            print(causes_markdown(), end="")
        else:
            for code, (layer, meaning, fix, _) in CAUSES.items():
                print(f"{code} [{layer}]\n    {meaning}\n    fix: {fix}")
        return 0

    from .demo import run_demo
    return run_demo()


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return _run(args)
    except CacheAutopsyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except BrokenPipeError:  # e.g. `| head`
        return 0


if __name__ == "__main__":
    sys.exit(main())
