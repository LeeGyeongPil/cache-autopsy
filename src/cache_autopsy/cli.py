"""Command line entry point. Exit codes: 0 ok, 1 gate failed, 2 input error."""
from __future__ import annotations

import argparse
import os
import sys

from . import __version__, i18n
from .cost import Pricing
from .diff import diff_requests
from .lint import has_problems, lint_request
from .i18n import t
from .model import CacheAutopsyError
from .records import read_jsonl, read_request
from .report import analysis_json, analysis_md, analysis_text, divergence_text, findings_text
from .rules import CAUSES, causes_markdown
from .verdict import DEFAULT_MIN_TOKENS, analyze_records

PROVIDER_CHOICES = ["auto", "anthropic", "openai_chat", "openai_responses"]


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="cache-autopsy", description=t("help.description"))
    p.add_argument("--version", action="version", version=f"cache-autopsy {__version__}")
    p.add_argument("--lang", choices=i18n.LANGS, help=t("help.lang"))
    sub = p.add_subparsers(dest="cmd", required=True)

    def lang(sp):  # also accepted after the subcommand; SUPPRESS keeps a value given before it
        sp.add_argument("--lang", choices=i18n.LANGS, default=argparse.SUPPRESS, help=t("help.lang"))

    def common(sp, fmt=True):
        sp.add_argument("--provider", choices=PROVIDER_CHOICES, default="auto", help=t("help.provider"))
        sp.add_argument("--context", type=int, default=40, help=t("help.context"))
        sp.add_argument("--redact", action="store_true", help=t("help.redact"))
        if fmt:
            sp.add_argument("--format", choices=["text", "json", "md"], default="text")
        lang(sp)

    d = sub.add_parser("diff", help=t("help.diff"))
    d.add_argument("a"), d.add_argument("b")
    common(d)

    a = sub.add_parser("analyze", help=t("help.analyze"))
    a.add_argument("log")
    common(a)
    a.add_argument("--pricing", help=t("help.pricing"))
    a.add_argument("--session-key", help=t("help.session_key"))
    a.add_argument("--min-tokens", type=int, default=DEFAULT_MIN_TOKENS, help=t("help.min_tokens"))
    a.add_argument("--fail-under", type=float, help=t("help.fail_under"))
    a.add_argument("--fail-on", help=t("help.fail_on"))

    l = sub.add_parser("lint", help=t("help.lint"))
    l.add_argument("request")
    common(l, fmt=False)
    l.add_argument("--min-tokens", type=int, default=DEFAULT_MIN_TOKENS)

    c = sub.add_parser("causes", help=t("help.causes"))
    c.add_argument("--format", choices=["text", "md"], default="text")
    lang(c)

    dm = sub.add_parser("demo", help=t("help.demo"))
    lang(dm)
    return p


def _provider(args) -> str | None:
    return None if args.provider == "auto" else args.provider


VERDICTS = {"hit", "expected_hit", "explained_miss", "unexplained_miss", "unexplained"}


def _check_gate_options(args) -> set[str]:
    """Validate --fail-under / --fail-on before any work so a typo cannot silently disable the gate."""
    if args.fail_under is not None and not 0 <= args.fail_under <= 1:
        raise CacheAutopsyError.coded("err.fail_under_range", value=args.fail_under)
    wanted = {w.strip() for w in (args.fail_on or "").split(",") if w.strip()}
    unknown = sorted(wanted - set(CAUSES) - VERDICTS)
    if unknown:
        raise CacheAutopsyError.coded("err.fail_on_unknown", values=", ".join(unknown),
                                      verdicts=", ".join(sorted(VERDICTS)))
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
            print(t("cli.no_records", path=args.log), file=sys.stderr)
        render = {"text": analysis_text, "json": analysis_json, "md": analysis_md}[args.format]
        print(render(report, args.redact))
        failed = False
        rate = report.summary["hit_rate"]
        if args.fail_under is not None:
            if rate is None:
                print(t("cli.no_usage"), file=sys.stderr)
                return 2
            if rate < args.fail_under:
                print(t("cli.fail_rate", rate=f"{rate:.2f}", limit=f"{args.fail_under:.2f}"), file=sys.stderr)
                failed = True
        if args.fail_on:
            hits = [p for p in report.pairs if p.verdict in wanted or wanted & set(p.causes) or p.reason in wanted]
            if hits:
                print(t("cli.fail_on", count=len(hits), wanted=args.fail_on), file=sys.stderr)
                failed = True
        return 1 if failed else 0

    if args.cmd == "lint":
        findings = lint_request(read_request(args.request), _provider(args), args.min_tokens)
        print(findings_text(findings))
        return 1 if has_problems(findings) else 0

    if args.cmd == "causes":
        if args.format == "md":
            print(causes_markdown(i18n.current_lang()), end="")
        else:
            for code, (layer, *_rest) in CAUSES.items():
                print(t("cli.causes_row", code=code, layer=layer, meaning=t(f"cause.{code}.meaning"),
                          fix=t(f"cause.{code}.fix")))
        return 0

    from .demo import run_demo
    return run_demo()


def _early_lang(argv: list[str] | None) -> str:
    """Language for the help texts, read before the real parser is built (--lang beats the environment)."""
    pre = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    pre.add_argument("--lang")
    known, _ = pre.parse_known_args(argv)
    return i18n.resolve_lang(known.lang, os.environ)


def main(argv: list[str] | None = None) -> int:
    i18n.set_lang(_early_lang(argv))
    args = _parser().parse_args(argv)
    i18n.set_lang(i18n.resolve_lang(args.lang, os.environ))  # normally the same; a trailing --lang wins
    try:
        return _run(args)
    except CacheAutopsyError as exc:
        print(t("cli.error", detail=exc.localized()), file=sys.stderr)
        return 2
    except BrokenPipeError:  # e.g. `| head`
        return 0


if __name__ == "__main__":
    sys.exit(main())
