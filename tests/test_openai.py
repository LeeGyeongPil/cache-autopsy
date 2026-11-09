import unittest

from _helpers import records
from cache_autopsy import analyze_records


class OpenAITest(unittest.TestCase):
    def test_setting_changes_and_diagnostics(self):  # AC-6
        chat = analyze_records(records("openai_chat.jsonl")).pairs
        self.assertEqual(chat[1].reason, "reasoning_effort_changed")
        self.assertEqual(chat[2].reason, "text_format_changed")
        self.assertEqual(chat[2].provider_diagnostic, "text_format_changed")
        self.assertIs(chat[2].agree, True)
        self.assertIsNone(chat[1].agree)
        resp = analyze_records(records("openai_responses.jsonl")).pairs
        self.assertEqual(resp[1].reason, "reasoning_effort_changed")
        self.assertEqual(resp[2].reason, "text_format_changed")
        self.assertIn("setting_changed:text.format", resp[2].causes)
        anthropic = analyze_records(records("anthropic_broken.jsonl")).pairs[6]
        self.assertEqual(anthropic.reason, "messages_changed")
        self.assertIn("setting_changed:tool_choice", anthropic.causes)

    def test_disagreeing_diagnostic_is_flagged(self):
        recs = records("openai_chat.jsonl")
        recs[3]["response"]["prompt_cache_diagnostics"]["reason"] = "model_changed"
        self.assertIs(analyze_records(recs).pairs[2].agree, False)

    def test_provider_detection_and_forcing(self):
        self.assertEqual(analyze_records(records("openai_chat.jsonl")).pairs[0].provider, "openai_chat")
        self.assertEqual(analyze_records(records("openai_responses.jsonl")).pairs[0].provider, "openai_responses")
        self.assertEqual(analyze_records(records("anthropic_fixed.jsonl")).pairs[0].provider, "anthropic")
        forced = analyze_records(records("openai_chat.jsonl"), provider="openai_chat")
        self.assertEqual(forced.pairs[0].provider, "openai_chat")

    def test_prompt_cache_key_change(self):
        recs = records("openai_chat.jsonl")[:2]
        recs[1]["request"]["prompt_cache_key"] = "other"
        self.assertEqual(analyze_records(recs).pairs[0].reason, "prompt_cache_key_changed")


if __name__ == "__main__":
    unittest.main()
