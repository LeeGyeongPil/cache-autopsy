"""English / Korean output: message table parity, language choice, translated errors, unchanged JSON."""
import contextlib
import io
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from _helpers import SAMPLES
from cache_autopsy import i18n
from cache_autopsy.cli import main
from cache_autopsy.lint import lint_request
from cache_autopsy.model import InputFormatError
from cache_autopsy.rules import CAUSES, fix_for

BROKEN = str(SAMPLES / "anthropic_broken.jsonl")
VOLATILE = str(SAMPLES / "requests/volatile_system.json")
TOOLS_A = str(SAMPLES / "requests/tools_a.json")
TOOLS_B = str(SAMPLES / "requests/tools_b.json")
HANGUL = re.compile("[가-힣]")


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


def placeholders(text):
    return set(re.findall(r"\{(\w+)", text))


# ---- message table ----

def test_en_and_ko_have_the_same_keys():
    en, ko = i18n.MESSAGES["en"], i18n.MESSAGES["ko"]
    assert set(en) == set(ko), sorted(set(en) ^ set(ko))


def test_placeholders_match_between_languages():
    for key, text in i18n.MESSAGES["en"].items():
        assert placeholders(text) == placeholders(i18n.MESSAGES["ko"][key]), key


def test_every_cause_has_korean_meaning_and_fix():
    for code, (_layer, meaning, fix, _src) in CAUSES.items():
        assert i18n.MESSAGES["en"][f"cause.{code}.meaning"] == meaning
        assert i18n.MESSAGES["en"][f"cause.{code}.fix"] == fix
        for part in ("meaning", "fix"):
            assert HANGUL.search(i18n.MESSAGES["ko"][f"cause.{code}.{part}"]), (code, part)


def test_korean_messages_are_not_left_in_english():
    # a value without any Hangul is only allowed when it is a pure technical token
    allowed = {"rep.col_byte", "div.byte", "div.byte_na"}
    for key, text in i18n.MESSAGES["ko"].items():
        if key not in allowed and not key.startswith("cause."):
            assert HANGUL.search(text), key


# ---- choosing the language ----

@pytest.mark.parametrize("cli,env,expected", [
    (None, {}, "en"),
    ("ko", {}, "ko"),
    ("en", {"CACHE_AUTOPSY_LANG": "ko"}, "en"),
    (None, {"CACHE_AUTOPSY_LANG": "ko", "LC_ALL": "en_US.UTF-8"}, "ko"),
    (None, {"CACHE_AUTOPSY_LANG": "en", "LC_ALL": "ko_KR.UTF-8"}, "en"),
    (None, {"LC_ALL": "ko_KR.UTF-8", "LC_MESSAGES": "en_US", "LANG": "en_US"}, "ko"),
    (None, {"LC_ALL": "en_US.UTF-8", "LC_MESSAGES": "ko_KR", "LANG": "ko_KR"}, "en"),
    (None, {"LC_MESSAGES": "ko_KR.UTF-8", "LANG": "en_US"}, "ko"),
    (None, {"LC_ALL": "", "LC_MESSAGES": "", "LANG": "ko_KR.UTF-8"}, "ko"),
    (None, {"LANG": "ko_KR.UTF-8"}, "ko"),
    (None, {"LANG": "C"}, "en"),
    (None, {"LANG": "POSIX"}, "en"),
    (None, {"LANG": "en_US.UTF-8"}, "en"),
    (None, {"CACHE_AUTOPSY_LANG": "klingon", "LANG": "ko_KR"}, "en"),
    (None, {"CACHE_AUTOPSY_LANG": ""}, "en"),
])
def test_resolve_lang_priority(cli, env, expected):
    assert i18n.resolve_lang(cli, env) == expected


def test_lang_flag_works_before_and_after_the_subcommand():
    _, before, _ = run("--lang", "ko", "analyze", BROKEN)
    _, after, _ = run("analyze", BROKEN, "--lang", "ko")
    assert before == after
    assert "적중률" in before and "hit rate" not in before


def test_lang_env_var_and_lang_variable(monkeypatch):
    monkeypatch.setenv("CACHE_AUTOPSY_LANG", "ko")
    assert "적중률" in run("analyze", BROKEN)[1]
    monkeypatch.delenv("CACHE_AUTOPSY_LANG")
    monkeypatch.setenv("LANG", "ko_KR.UTF-8")
    assert "적중률" in run("analyze", BROKEN)[1]
    assert "연습용" in run("demo")[1].splitlines()[0]


def test_lang_flag_beats_environment(monkeypatch):
    monkeypatch.setenv("LANG", "ko_KR.UTF-8")
    out = run("--lang", "en", "analyze", BROKEN)[1]
    assert "hit rate" in out and not HANGUL.search(out.replace("한", ""))


def test_invalid_lang_flag_is_an_argparse_error():
    with pytest.raises(SystemExit) as info, contextlib.redirect_stderr(io.StringIO()):
        main(["--lang", "fr", "demo"])
    assert info.value.code == 2


def test_help_is_translated():
    out = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stdout(out):
        main(["--lang", "ko", "-h"])
    assert "프롬프트 캐시" in out.getvalue()
    out = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stdout(out):
        main(["analyze", "-h"])
    assert "--lang" in out.getvalue()
    out = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stdout(out):
        main(["-h"])
    assert " ".join(out.getvalue().split()).count("hit rate, missed cost and causes for a JSONL call log") == 1


# ---- every command in Korean ----

def test_korean_commands():
    code, out, _ = run("--lang", "ko", "diff", TOOLS_A, TOOLS_B)
    assert code == 0 and "이유" in out and "해결" in out and "tool_order_changed" in out
    code, out, _ = run("--lang", "ko", "lint", VOLATILE)
    assert code == 1 and "WARNING" in out and "해결:" in out and "경고" in out
    code, out, _ = run("--lang", "ko", "causes")
    assert "해결:" in out and "tool_order_changed" in out
    code, out, _ = run("--lang", "ko", "causes", "--format", "md")
    assert "# 원인 코드" in out
    code, out, err = run("--lang", "ko", "analyze", BROKEN, "--fail-under", "0.6", "--fail-on", "timestamp_in_prefix")
    assert code == 1 and "FAIL: 적중률 0.12 < 0.60" in err and "FAIL: 비교 1건" in err
    code, out, _ = run("--lang", "ko", "analyze", BROKEN, "--format", "md")
    assert "## cache-autopsy 보고서" in out


def test_english_default_has_no_korean():
    for argv in (("demo",), ("analyze", BROKEN), ("diff", TOOLS_A, TOOLS_B), ("lint", VOLATILE), ("causes",),
                 ("causes", "--format", "md"), ("analyze", BROKEN, "--format", "md")):
        assert not HANGUL.search(run(*argv)[1]), argv


def test_empty_pricing_gap_and_cost_unavailable_in_korean(tmp_path):
    empty = tmp_path / "logs" / "empty.jsonl"
    empty.parent.mkdir()
    empty.write_text("")
    code, _, err = run("--lang", "ko", "analyze", str(empty))
    assert code == 0 and "경고:" in err and str(empty) in err


# ---- machine output does not change ----

@pytest.mark.parametrize("argv", [
    ("analyze", BROKEN, "--format", "json"),
    ("diff", TOOLS_A, TOOLS_B, "--format", "json"),
])
def test_json_is_identical_in_both_languages(argv):
    _, en, _ = run(*argv)
    _, ko, _ = run("--lang", "ko", *argv)
    assert en == ko
    json.loads(en)
    assert not HANGUL.search(en)


def test_library_api_stays_english():
    i18n.set_lang("ko")
    findings = lint_request(json.loads(Path(VOLATILE).read_text()))
    assert findings and all(not HANGUL.search(f.message + f.fix) for f in findings)
    assert "msg_key" not in findings[0].to_dict() and "msg_params" not in findings[0].to_dict()
    assert fix_for(["tool_order_changed"], "tools_changed") == CAUSES["tool_order_changed"][2]
    raise_it = InputFormatError.coded("err.file_not_found", 3, path="x.jsonl")
    assert str(raise_it) == "line 3: file not found: x.jsonl. Check the path."
    assert HANGUL.search(raise_it.localized())


# ---- OSError paths: exit 2, our own line, no traceback, the path as given ----

def _error_cases(tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir()
    missing = str(logs / "missing.jsonl")
    cases = [
        ("missing log", ("analyze", missing), missing),
        ("directory", ("analyze", str(logs)), str(logs)),
        ("missing pricing", ("analyze", BROKEN, "--pricing", str(logs / "prices.json")), str(logs / "prices.json")),
        ("missing diff request", ("diff", missing, TOOLS_B), missing),
        ("missing lint request", ("lint", missing), missing),
    ]
    locked = logs / "locked.jsonl"
    locked.write_text("{}\n")
    locked.chmod(0)
    if not os.access(locked, os.R_OK):  # root can read anything: skip only this case
        cases.append(("no permission", ("analyze", str(locked)), str(locked)))
    return cases, locked


@pytest.mark.parametrize("lang,prefix", [("en", "error: "), ("ko", "오류: ")])
def test_os_errors_are_translated_without_traceback(tmp_path, lang, prefix):
    cases, locked = _error_cases(tmp_path)
    try:
        for name, argv, shown in cases:
            code, out, err = run("--lang", lang, *argv)
            assert code == 2, name
            assert err.startswith(prefix), (name, err)
            assert "Traceback" not in err and shown in err, (name, err)
            if lang == "ko":
                assert HANGUL.search(err.split(shown)[0] + err.split(shown)[-1]), name
            else:
                assert not HANGUL.search(err), name
    finally:
        locked.chmod(0o600)


def test_subprocess_korean_error_has_no_traceback(tmp_path):
    src = Path(__file__).resolve().parent.parent / "src"
    env = {**os.environ, "PYTHONPATH": str(src)}
    for name in ("CACHE_AUTOPSY_LANG", "LC_ALL", "LC_MESSAGES"):
        env.pop(name, None)
    env["LANG"] = "C"
    gone = str(tmp_path / "logs" / "missing.jsonl")
    done = subprocess.run([sys.executable, "-m", "cache_autopsy", "--lang", "ko", "analyze", gone],
                          capture_output=True, text=True, env=env, timeout=60)
    assert done.returncode == 2
    assert "Traceback" not in done.stderr
    assert done.stderr.startswith("오류:") and gone in done.stderr


def test_line_number_prefix_is_translated(tmp_path):
    bad = tmp_path / "logs" / "bad.jsonl"
    bad.parent.mkdir()
    bad.write_text(Path(BROKEN).read_text().splitlines()[0] + "\n{oops\n")
    assert "line 2: invalid JSON" in run("analyze", str(bad))[2]
    assert "2행:" in run("--lang", "ko", "analyze", str(bad))[2]


def test_usage_error_inside_record_keeps_line_and_translation(tmp_path):
    rec = {"request": {"model": "claude-x", "messages": []}, "response": {"usage": {"input_tokens": -1}}}
    log = tmp_path / "logs" / "usage.jsonl"
    log.parent.mkdir()
    log.write_text(json.dumps(rec) + "\n")
    err_en = run("analyze", str(log))[2]
    err_ko = run("--lang", "ko", "analyze", str(log))[2]
    assert "line 1: usage.input_tokens must be a non-negative integer" in err_en
    assert "1행:" in err_ko and "0 이상의 정수" in err_ko


def test_os_and_json_details_are_korean_for_common_cases(tmp_path):
    bad = tmp_path / "logs" / "bad.jsonl"
    bad.parent.mkdir()
    bad.write_text("{nope\n", encoding="utf-8")
    code, out, err = run("--lang", "ko", "analyze", str(tmp_path))
    assert code == 2 and "디렉터리입니다" in err and "Is a directory" not in err
    code, out, err = run("--lang", "ko", "analyze", str(bad))
    assert code == 2 and "Expecting" not in err and "속성 이름" in err
    code, out, err = run("--lang", "en", "analyze", str(tmp_path))
    assert "Is a directory" in err
    assert i18n.localize_detail("something unknown", "ko") == "something unknown"
