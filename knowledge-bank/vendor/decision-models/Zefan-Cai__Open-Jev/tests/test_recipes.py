import unittest

from jev.api import candidate_prompts, compile_request
from jev import recipes as r


class RecipesTest(unittest.TestCase):
    def test_all_public_examples_compile_without_generation(self):
        for name, builder in r.EXAMPLES.items():
            with self.subTest(name=name):
                request = builder()
                records = compile_request(**request)
                self.assertTrue(records)
                self.assertTrue(all(candidate_prompts(row) for row in records))

    def test_extraction_is_verbatim_and_missing_value_stays_missing(self):
        text = "Old: a@example.org. Billing: b@example.org."
        spans = r.extract_candidates(text, "email")
        for span in spans.values():
            self.assertEqual(text[span["start"]:span["end"]], span["text"])
        self.assertIsNone(r.selected_span(text, "email", {"answers": {"span": {"choice": "none"}}}))
        with self.assertRaises(ValueError):
            r.selected_span(text, "email", {"answers": {"span": {"choice": "invented"}}})
        request = r.value_extraction("No contact listed", "email")
        self.assertEqual(list(request["questions"]["span"]["criteria"]), ["none"])

    def test_date_reference_rollover_and_invalid_dates(self):
        candidates = list(r.date_candidates("Tomorrow, not 2026-02-30.", "2026-12-31").values())
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["iso"], "2027-01-01")

    def test_speculative_tool_args_are_not_executed_or_mixed(self):
        functions = {"lamp": {"description": "Lamp", "arguments": {"level": {"low": "Low"}}},
                     "fan": {"description": "Fan", "arguments": {"speed": {"fast": "Fast"}}}}
        response = {"answers": {"function": {"choice": "lamp"}, "lamp/level": {"choice": "low"},
                                 "fan/speed": {"choice": "fast"}}}
        self.assertEqual(r.selected_function(functions, response),
                         {"function": "lamp", "arguments": {"level": "low"}, "requires_review": False})
        response["answers"]["lamp/level"]["choice"] = "__missing__"
        self.assertTrue(r.selected_function(functions, response)["requires_review"])

    def test_markdown_preserves_code_with_fences(self):
        block = "```example```"
        rendered = r.render_markdown([block], {"answers": {"block_0": {"choice": "code"}}})
        self.assertEqual(rendered, "````\n" + block + "\n````")

    def test_tool_key_collisions_and_reserved_candidates_rejected(self):
        for name, argument, values in (("a/b", "c", {"ok": "Ok"}),
                                        ("a", "b/c", {"ok": "Ok"}),
                                        ("a", "b", {"__missing__": "User label"})):
            with self.assertRaises(ValueError):
                r.function_calling("test", {name: {"description": "Test", "arguments": {argument: values}}})

    def test_multiline_quote_and_list_retain_structure(self):
        for kind, expected in (("quote", "> first\n> second"), ("bullet", "- first\n  second"),
                               ("numbered", "1. first\n   second")):
            self.assertEqual(r.render_markdown(["first\nsecond"],
                             {"answers": {"block_0": {"choice": kind}}}), expected)


if __name__ == "__main__":
    unittest.main()
