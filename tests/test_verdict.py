import unittest

from _helpers import records
from cache_autopsy import Pricing, analyze_records
from cache_autopsy.model import InputFormatError


class VerdictTest(unittest.TestCase):
    def test_unexplained_miss(self):  # AC-5
        pairs = analyze_records(records("anthropic_broken.jsonl")).pairs
        self.assertEqual(pairs[0].verdict, "hit")
        ttl, provider = pairs[4], pairs[5]
        self.assertEqual((ttl.verdict, ttl.reason, ttl.causes), ("unexplained_miss", "unexplained", ["ttl_expired_suspected"]))
        self.assertEqual(ttl.gap_seconds, 420)
        self.assertEqual((provider.verdict, provider.causes), ("unexplained_miss", ["provider_side_suspected"]))

    def test_below_min_tokens_is_suspected(self):
        recs = records("anthropic_broken.jsonl")[4:6]
        recs[0]["response"]["usage"].update(cache_creation_input_tokens=100)
        pairs = analyze_records(recs).pairs
        self.assertEqual(pairs[0].causes, ["below_min_tokens"])

    def test_explained_miss_has_cost(self):
        pair = analyze_records(records("anthropic_broken.jsonl")).pairs[1]
        self.assertEqual(pair.verdict, "explained_miss")
        self.assertEqual(pair.missed_tokens, 3440)
        # the miss costs (price of what was paid instead of a cache read), so it must be positive
        self.assertGreater(pair.missed_cost_usd, 0)

    def test_fixed_session_has_no_misses(self):
        rep = analyze_records(records("anthropic_fixed.jsonl"))
        self.assertEqual(rep.summary["missed_tokens"], 0)
        self.assertGreater(rep.summary["hit_rate"], analyze_records(records("anthropic_broken.jsonl")).summary["hit_rate"])

    def test_unknown_model_reports_tokens_only(self):
        recs = records("anthropic_broken.jsonl")[:3]
        for r in recs:
            r["request"]["model"] = "claude-unreleased-9"
        rep = analyze_records(recs)
        self.assertIsNone(rep.summary["missed_cost_usd"])
        self.assertIn("claude-unreleased-9", rep.summary["unpriced_models"])
        self.assertGreater(rep.summary["missed_tokens"], 0)

    def test_session_key(self):
        recs = records("anthropic_broken.jsonl")
        for i, r in enumerate(recs):
            r["request"]["metadata"] = {"user_id": "a" if i % 2 == 0 else "b"}
            r.pop("session_id")
        rep = analyze_records(recs, session_key="request.metadata.user_id")
        self.assertEqual({s["id"] for s in rep.sessions}, {"a", "b"})

    def test_pricing_override(self):
        pricing = Pricing({"_meta": {}, "anthropic": {"claude-sonnet-4-5": {"input": 30.0, "cache_write_5m": 37.5,
                                                                         "cache_write_1h": 60.0, "cache_read": 3.0}},
                           "openai": {}})
        base = analyze_records(records("anthropic_broken.jsonl")).summary["missed_cost_usd"]
        ten = analyze_records(records("anthropic_broken.jsonl"), pricing=pricing).summary["missed_cost_usd"]
        self.assertAlmostEqual(ten, base * 10, places=3)

    def test_non_dict_record_is_an_input_error(self):  # Q-4
        with self.assertRaises(InputFormatError):
            analyze_records([1])


if __name__ == "__main__":
    unittest.main()
