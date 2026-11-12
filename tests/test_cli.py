import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from _helpers import SAMPLES
from cache_autopsy.cli import main


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


BROKEN = str(SAMPLES / "anthropic_broken.jsonl")
FIXED = str(SAMPLES / "anthropic_fixed.jsonl")


class CliTest(unittest.TestCase):
    def test_demo(self):  # AC-1
        code, out, _ = run("demo")
        self.assertEqual(code, 0)
        self.assertIn("practice mock data", out.splitlines()[0])
        self.assertNotIn("연습용", out)
        code, ko_out, _ = run("--lang", "ko", "demo")
        self.assertEqual(code, 0)
        self.assertIn("연습용 목(mock)", ko_out.splitlines()[0])
        rows = {line.split()[0]: line for line in out.splitlines() if line.startswith(("broken", "fixed"))}
        self.assertEqual(set(rows), {"broken", "fixed"})
        rate = lambda row: float(row.split()[2].rstrip("%"))
        self.assertGreater(rate(rows["fixed"]), rate(rows["broken"]))

    def test_diff_command(self):  # AC-2
        code, out, _ = run("diff", str(SAMPLES / "requests/tools_a.json"), str(SAMPLES / "requests/tools_b.json"))
        self.assertEqual(code, 0)
        for text in ("tools_changed", "tool_order_changed", "tools[0]", "byte="):
            self.assertIn(text, out)

    def test_gate(self):  # AC-8
        code, _, err = run("analyze", BROKEN, "--fail-under", "0.6")
        self.assertEqual(code, 1)
        self.assertIn("hit rate 0.12 < 0.60", err)
        self.assertEqual(run("analyze", FIXED, "--fail-under", "0.6")[0], 0)

    def test_fail_on(self):
        self.assertEqual(run("analyze", BROKEN, "--fail-on", "timestamp_in_prefix")[0], 1)
        self.assertEqual(run("analyze", FIXED, "--fail-on", "timestamp_in_prefix,tool_order_changed")[0], 0)

    def test_broken_file_reports_line_and_exit_2(self):  # AC-8
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp, "bad.jsonl")
            bad.write_text(Path(BROKEN).read_text().splitlines()[0] + "\n{oops\n")
            code, _, err = run("analyze", str(bad))
        self.assertEqual(code, 2)
        self.assertIn("line 2", err)
        code, _, err = run("analyze", "/nonexistent/file.jsonl")
        self.assertEqual(code, 2)
        self.assertIn("file not found", err)

    def test_json_and_md_output(self):  # AC-9
        code, out, _ = run("analyze", BROKEN, "--format", "json")
        self.assertEqual(code, 0)
        data = json.loads(out)
        for key in ("hit_rate", "missed_tokens", "missed_cost_usd"):
            self.assertIn(key, data["summary"])
        for key in ("verdict", "reason", "json_path", "tokens_estimated"):
            self.assertIn(key, data["pairs"][0])
        code, out, _ = run("analyze", BROKEN, "--format", "md")
        self.assertIn("| session | # | verdict |", out)

    def test_redact_hides_request_text(self):
        _, out, _ = run("analyze", BROKEN, "--redact")
        self.assertNotIn("search_orders", out)

    def test_lint_exit_codes(self):  # AC-7
        code, out, _ = run("lint", str(SAMPLES / "requests/volatile_system.json"))
        self.assertEqual(code, 1)
        self.assertIn("timestamp_in_prefix", out)
        self.assertIn("system[0].text", out)
        self.assertIn("breakpoint_on_volatile_block", out)
        self.assertEqual(run("lint", str(SAMPLES / "requests/clean.json"))[0], 0)

    def test_causes(self):
        code, out, _ = run("causes")
        self.assertEqual(code, 0)
        self.assertIn("tool_order_changed", out)

    def test_pricing_file_errors(self):
        code, _, err = run("analyze", BROKEN, "--pricing", "/nonexistent.json")
        self.assertEqual(code, 2)
        self.assertIn("pricing file not found", err)

    def test_non_utf8_and_directory_inputs_exit_2(self):  # Q-2
        with tempfile.TemporaryDirectory() as d:
            bad = Path(d) / "latin.jsonl"
            bad.write_bytes(bytes([0xFF, 0xFE, 0x00]) + b"bad\n")
            for argv in (("analyze", str(bad)), ("analyze", d), ("lint", str(bad)), ("lint", d),
                         ("diff", str(bad), str(bad)), ("analyze", BROKEN, "--pricing", str(bad))):
                code, _, err = run(*argv)
                self.assertEqual(code, 2, argv)
                self.assertIn("error:", err)
                self.assertNotIn("Traceback", err)

    def test_gate_option_validation(self):  # Q-3
        code, _, err = run("analyze", BROKEN, "--fail-on", "nonsense_code")
        self.assertEqual(code, 2)
        self.assertIn("cache-autopsy causes", err)
        code, _, err = run("analyze", BROKEN, "--fail-under", "60")
        self.assertEqual(code, 2)
        self.assertIn("0.6", err)

    def test_empty_log_warns(self):  # Q-3
        with tempfile.TemporaryDirectory() as d:
            empty = Path(d) / "empty.jsonl"
            empty.write_text("")
            code, _, err = run("analyze", str(empty))
            self.assertEqual(code, 0)
            self.assertIn("no records in", err)


if __name__ == "__main__":
    unittest.main()
