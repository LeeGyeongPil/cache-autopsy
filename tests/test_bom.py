"""Regression tests: inputs starting with a UTF-8 BOM must be accepted (0.1.1)."""
import contextlib
import io
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


def write_pair(tmp, src, name):
    """Copy a sample twice: with a BOM and without one."""
    text = Path(src).read_text(encoding="utf-8")
    bom, plain = Path(tmp) / f"bom_{name}", Path(tmp) / f"plain_{name}"
    bom.write_text(text, encoding="utf-8-sig")
    plain.write_text(text, encoding="utf-8")
    assert bom.read_bytes()[:3] == b"\xef\xbb\xbf" and plain.read_bytes()[:3] != b"\xef\xbb\xbf"
    return str(bom), str(plain)


class BomTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = self._tmp.name

    def test_analyze_jsonl_with_bom(self):  # AC-1
        bom, plain = write_pair(self.tmp, SAMPLES / "anthropic_broken.jsonl", "log.jsonl")
        code, out, _ = run("analyze", bom)
        code_plain, out_plain, _ = run("analyze", plain)
        self.assertEqual((code, code_plain), (0, 0))
        self.assertIn("12.1%", out)
        self.assertIn("21,110", out)
        # Same report apart from the file name echoed in the header.
        self.assertEqual(out.replace(bom, "X"), out_plain.replace(plain, "X"))

    def test_lint_and_diff_request_with_bom(self):  # AC-2
        bom, plain = write_pair(self.tmp, SAMPLES / "requests/clean.json", "clean.json")
        code, out, _ = run("lint", bom)
        self.assertEqual(code, 0)
        self.assertIn("no findings", out)
        code, _, err = run("diff", bom, plain)
        self.assertEqual(code, 0, err)

    def test_pricing_file_with_bom(self):  # AC-3
        bom, plain = write_pair(self.tmp, SAMPLES.parent / "pricing.json", "pricing.json")
        log = str(SAMPLES / "anthropic_broken.jsonl")
        code, out, err = run("analyze", log, "--pricing", bom)
        code_plain, out_plain, _ = run("analyze", log, "--pricing", plain)
        self.assertEqual((code, code_plain), (0, 0), err)
        self.assertEqual(out.replace(bom, "X"), out_plain.replace(plain, "X"))

    def test_bad_input_still_exits_2(self):  # AC-4
        bad = Path(self.tmp) / "bad.json"
        bad.write_text("{not json", encoding="utf-8-sig")
        latin = Path(self.tmp) / "latin.jsonl"
        latin.write_bytes(b'{"a": "\xff\xfe"}\n')
        for argv in (("analyze", str(bad)), ("lint", str(bad)), ("analyze", str(latin)),
                     ("analyze", str(SAMPLES / "anthropic_broken.jsonl"), "--pricing", str(bad))):
            code, _, _ = run(*argv)
            self.assertEqual(code, 2, argv)


if __name__ == "__main__":
    unittest.main()
