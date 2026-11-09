import unittest

from _helpers import records, request
from cache_autopsy import InputFormatError, UnknownProviderError, diff_requests


class DiffTest(unittest.TestCase):
    def test_tool_order_changed(self):  # AC-2
        d = diff_requests(request("tools_a.json"), request("tools_b.json"))
        self.assertEqual(d.reason, "tools_changed")
        self.assertEqual(d.causes, ["tool_order_changed"])
        self.assertTrue(d.json_path.startswith("tools[0]"))
        self.assertIsInstance(d.byte_offset, int)
        self.assertTrue(d.context_before and d.context_after)

    def test_probe_session_causes(self):  # AC-3
        calls = [r["request"] for r in records("anthropic_broken.jsonl")[:5]]
        expected = [
            ("messages_changed", "append_only_ok", "messages[1]"),
            ("tools_changed", "tool_order_changed", "tools[0]"),
            ("system_changed", "timestamp_in_prefix", "system"),
            ("tools_changed", "json_key_order_changed", "tools[0].input_schema"),
        ]
        for i, (reason, cause, path) in enumerate(expected):
            d = diff_requests(calls[i], calls[i + 1])
            self.assertEqual(d.reason, reason, i)
            self.assertIn(cause, d.causes, i)
            self.assertTrue(d.json_path.startswith(path), (i, d.json_path))

    def test_identical_requests(self):
        req = request("tools_a.json")
        d = diff_requests(req, dict(req))
        self.assertEqual(d.reason, "unchanged")
        self.assertTrue(d.prefix_intact)

    def test_model_change_wins(self):
        a = request("tools_a.json")
        b = dict(a, model="claude-haiku-4-5")
        self.assertEqual(diff_requests(a, b).reason, "model_changed")

    def test_non_ascii_byte_offset_counts_bytes(self):
        a = {"model": "claude-x", "system": "안녕 hello", "messages": []}
        b = {"model": "claude-x", "system": "안녕 world", "messages": []}
        d = diff_requests(a, b)
        # "model":"claude-x" ... offsets are UTF-8 bytes, Korean letters take 3 bytes each
        self.assertGreater(d.byte_offset, len(d.context_before))

    def test_input_validation(self):
        with self.assertRaises(InputFormatError):
            diff_requests([], {})
        with self.assertRaises(UnknownProviderError):
            diff_requests({"foo": 1}, {"foo": 2})
        with self.assertRaises(UnknownProviderError):
            diff_requests({"foo": 1}, {"foo": 2}, provider="nope")


if __name__ == "__main__":
    unittest.main()
