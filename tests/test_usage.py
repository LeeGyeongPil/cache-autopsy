import unittest

from _helpers import records
from cache_autopsy import InputFormatError, analyze_records
from cache_autopsy.providers import get_provider


class UsageTest(unittest.TestCase):
    def test_hit_rates(self):  # AC-4
        probe = analyze_records(records("anthropic_broken.jsonl")[:5])
        self.assertAlmostEqual(probe.summary["hit_rate"], 3410 / 17465, places=6)
        self.assertGreater(probe.summary["hit_rate"], 0.19)  # NOT 0%: read / (read + write + input)
        chat = analyze_records(records("openai_chat.jsonl"))
        self.assertAlmostEqual(chat.summary["hit_rate"], (3328 + 3584) / (3400 + 3450 + 3500 + 3600 + 3650), places=6)
        resp = analyze_records(records("openai_responses.jsonl"))
        self.assertAlmostEqual(resp.summary["hit_rate"], 3328 / (3400 + 3450 + 3500 + 3550), places=6)

    def test_anthropic_usage_parts(self):
        rec = records("anthropic_broken.jsonl")[1]
        u = get_provider("anthropic").usage(rec["request"], rec["response"])
        self.assertEqual((u.total_input, u.cache_read, u.cache_write), (14 + 30 + 3410, 3410, 30))

    def test_estimate_when_no_usage(self):  # AC-10
        recs = records("anthropic_broken.jsonl")[:3]
        for r in recs:
            r["response"].pop("usage")
        rep = analyze_records(recs)
        self.assertIsNone(rep.summary["hit_rate"])
        self.assertTrue(rep.summary["tokens_estimated"])
        broken = [p for p in rep.pairs if p.verdict == "explained_miss"]
        self.assertTrue(broken and all(p.tokens_estimated and p.missed_tokens > 0 for p in broken))
        from cache_autopsy.report import analysis_text
        self.assertIn("~", analysis_text(rep))

    def test_bad_usage_is_reported_with_line(self):
        recs = records("anthropic_broken.jsonl")[:2]
        recs[1]["response"]["usage"]["input_tokens"] = -5
        with self.assertRaises(InputFormatError) as ctx:
            analyze_records(recs)
        self.assertEqual(ctx.exception.line, 2)

    def test_dependencies_are_empty(self):  # AC-10
        import tomllib
        from pathlib import Path
        meta = tomllib.loads((Path(__file__).resolve().parent.parent / "pyproject.toml").read_text())
        self.assertEqual(meta["project"]["dependencies"], [])


if __name__ == "__main__":
    unittest.main()
