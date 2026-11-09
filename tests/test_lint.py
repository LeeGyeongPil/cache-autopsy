import unittest

from _helpers import request
from cache_autopsy import lint_request
from cache_autopsy.lint import has_problems


class LintTest(unittest.TestCase):
    def test_volatile_system(self):  # AC-7
        findings = lint_request(request("volatile_system.json"))
        codes = {f.code: f for f in findings}
        self.assertEqual(codes["timestamp_in_prefix"].path, "system[0].text")
        self.assertIn("breakpoint_on_volatile_block", codes)
        self.assertTrue(has_problems(findings))

    def test_clean_request(self):  # AC-7
        self.assertEqual(lint_request(request("clean.json")), [])

    def test_too_many_breakpoints(self):
        req = request("clean.json")
        req["messages"] = [{"role": "user", "content": [{"type": "text", "text": f"m{i}", "cache_control": {"type": "ephemeral"}}]}
                           for i in range(4)]
        codes = [f.code for f in lint_request(req)]
        self.assertIn("too_many_breakpoints", codes)

    def test_uuid_in_tool_description(self):
        req = request("clean.json")
        req["tools"][0]["description"] += " id 123e4567-e89b-12d3-a456-426614174000"
        self.assertIn("uuid_in_prefix", [f.code for f in lint_request(req)])

    def test_short_prompt_is_info_only(self):
        req = {"model": "claude-sonnet-4-5", "max_tokens": 5, "cache_control": {"type": "ephemeral"},
               "system": "short", "messages": [{"role": "user", "content": "hi"}]}
        findings = lint_request(req)
        self.assertEqual([f.code for f in findings], ["below_min_tokens"])
        self.assertFalse(has_problems(findings))


if __name__ == "__main__":
    unittest.main()
