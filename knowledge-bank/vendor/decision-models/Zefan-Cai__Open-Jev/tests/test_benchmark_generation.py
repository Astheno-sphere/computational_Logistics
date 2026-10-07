import copy
from contextlib import redirect_stderr
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from jev.api import compile_request, format_response
from scripts.benchmark_generation import (InvalidOutput, comparable_ratio,
                                          generation_prompt, main, summarize,
                                          _timed_trial, validate_generation,
                                          validate_probability_mapping, validate_response)


class GenerationBenchmarkTest(unittest.TestCase):
    def setUp(self):
        self.request = {"state": "Please refund the duplicate payment; I am frustrated but civil.", "questions": {
            "category": {"type": "choice", "instructions": "Select the topic", "criteria": {"billing": "Charges or refunds", "technical": "Product malfunction"}},
            "refund": {"type": "noul", "instructions": "Does this explicitly request a refund?"},
            "tone": {"type": "score", "instructions": "Rate frustration", "criteria": ["Calm", "Frustrated but civil", "Very angry"]},
        }}
        self.response = format_response(compile_request(**self.request), [[0.9, 0.1], [0.05, 0.95], [0.1, 0.8, 0.1]])
        self.mapping = {"probabilities": {"category": {"billing": 0.9, "technical": 0.1},
                                          "refund": {"false": 0.05, "true": 0.95},
                                          "tone": {"0": 0.1, "1": 0.8, "2": 0.1}}}

    def test_complete_typed_response_and_json_validate(self):
        self.assertEqual(validate_response(self.request, self.response), self.response)
        self.assertEqual(validate_generation(self.request, json.dumps(self.response)), self.response)

    def test_parse_failure_is_not_repaired(self):
        for text in ("```json\n" + json.dumps(self.response) + "\n```", "not json", '{"answers":{},"answers":{}}', '{"answers":NaN}'):
            with self.assertRaises(InvalidOutput) as error:
                validate_generation(self.request, text)
            self.assertEqual(error.exception.category, "parse")

    def test_missing_questions_candidates_and_fields_are_coverage_failures(self):
        for mutate in (lambda a: a.pop("refund"), lambda a: a["category"]["probabilities"].pop("technical"),
                       lambda a: a["tone"].pop("confidence")):
            response = copy.deepcopy(self.response)
            mutate(response["answers"])
            with self.assertRaises(InvalidOutput) as error:
                validate_response(self.request, response)
            self.assertEqual(error.exception.category, "coverage")

    def test_bad_probabilities_and_derived_fields_are_schema_failures(self):
        for mutate in (lambda a: a["refund"].update(noul=True), lambda a: a["refund"].update(noul=2),
                       lambda a: a["tone"].update(score=0), lambda a: a["tone"].update(confidence=0),
                       lambda a: a["category"].update(choice="technical"),
                       lambda a: a["category"]["probabilities"].update(billing=0.1)):
            response = copy.deepcopy(self.response)
            mutate(response["answers"])
            with self.assertRaises(InvalidOutput) as error:
                validate_response(self.request, response)
            self.assertEqual(error.exception.category, "schema")

    def test_no_ratio_when_even_one_output_is_invalid(self):
        decision = summarize([{"status": "valid", "elapsed_seconds": 1}] * 3)
        generation = summarize([{"status": "valid", "elapsed_seconds": 3}] * 3)
        self.assertEqual(comparable_ratio(decision, generation), 3)
        invalid = summarize([{"status": "valid", "elapsed_seconds": 3}] * 2 +
                            [{"status": "invalid", "elapsed_seconds": 0.1, "failure_category": "parse"}])
        self.assertIsNone(comparable_ratio(decision, invalid))
        self.assertEqual(invalid["failures"]["parse"], 1)
        self.assertEqual(invalid["median_seconds_valid"], 3)

    def test_generation_prompt_contains_same_state_all_questions_and_full_output(self):
        prompt = generation_prompt(self.request)
        self.assertIn(self.request["state"], prompt)
        for key in self.request["questions"]:
            self.assertIn(key, prompt)
        for field in ("probabilities", "legend", "confidence", "noul"):
            self.assertIn(field, prompt)
        self.assertIn("EVERY", prompt)

    def test_probability_mapping_uses_identical_typed_formatter_without_mutation(self):
        original = copy.deepcopy(self.mapping)
        expected = format_response(compile_request(**self.request), [[0.9, 0.1], [0.05, 0.95], [0.1, 0.8, 0.1]])
        self.assertEqual(validate_probability_mapping(self.request, self.mapping), expected)
        self.assertEqual(validate_generation(self.request, json.dumps(self.mapping), "probabilities"), expected)
        self.assertEqual(self.mapping, original)

    def test_contracts_are_explicit_and_never_inferred_from_output(self):
        with self.assertRaises(InvalidOutput):
            validate_generation(self.request, json.dumps(self.mapping))
        with self.assertRaises(InvalidOutput):
            validate_generation(self.request, json.dumps(self.response), "probabilities")
        for function, argument in ((generation_prompt, None), (validate_generation, json.dumps(self.mapping))):
            with self.assertRaisesRegex(ValueError, "unknown output contract"):
                if argument is None:
                    function(self.request, "unsupported")
                else:
                    function(self.request, argument, "unsupported")

    def test_probability_mapping_requires_exact_question_and_candidate_coverage(self):
        for mutate in (lambda p: p.pop("refund"), lambda p: p.update(extra={"a": 1}),
                       lambda p: p["category"].pop("technical"),
                       lambda p: p["category"].update(extra=0),
                       lambda p: p.update(refund={"true": 0.95}),
                       lambda p: p.update(refund=0.95)):
            response = copy.deepcopy(self.mapping)
            mutate(response["probabilities"])
            with self.assertRaises(InvalidOutput) as error:
                validate_probability_mapping(self.request, response)
            self.assertEqual(error.exception.category, "coverage")
        with self.assertRaises(InvalidOutput):
            validate_probability_mapping(self.request, {**self.mapping, "confidence": 1})

    def test_probability_simplex_is_strict_and_invalid_numbers_are_not_repaired(self):
        for values in ({"billing": True, "technical": 0}, {"billing": "0.9", "technical": 0.1},
                       {"billing": float("nan"), "technical": 0},
                       {"billing": float("inf"), "technical": 0},
                       {"billing": -0.1, "technical": 1.1},
                       {"billing": 0, "technical": 0}, {"billing": 0.9, "technical": 0.0999}):
            response = copy.deepcopy(self.mapping)
            response["probabilities"]["category"] = values
            with self.assertRaises(InvalidOutput) as error:
                validate_probability_mapping(self.request, response)
            self.assertEqual(error.exception.category, "schema")

    def test_probability_json_rejects_fences_duplicate_keys_and_nonfinite_literals(self):
        valid = json.dumps(self.mapping)
        for text in ("```json\n" + valid + "\n```", valid + " trailing text",
                     '{"probabilities":{},"probabilities":{}}',
                     '{"probabilities":{"q":{"a":0,"a":1}}}',
                     '{"probabilities":NaN}', '{"probabilities":Infinity}'):
            with self.assertRaises(InvalidOutput) as error:
                validate_generation(self.request, text, "probabilities")
            self.assertEqual(error.exception.category, "parse")

    def test_probability_prompt_retains_request_and_omits_derived_output_fields(self):
        prompt = generation_prompt(self.request, "probabilities")
        self.assertIn(json.dumps(self.request, ensure_ascii=False), prompt)
        shape = json.loads(prompt.split("Required response shape:\n")[1])
        self.assertEqual(set(shape), {"probabilities"})
        self.assertEqual(set(shape["probabilities"]), set(self.request["questions"]))
        for record in compile_request(**self.request):
            self.assertEqual(set(shape["probabilities"][record["id"]]), set(record["answer_keys"]))
        self.assertIn("0.000001", prompt)

    def test_timed_probability_trials_retain_raw_text_on_success_and_failure(self):
        torch = Mock()
        torch.cuda.max_memory_allocated.return_value = 0
        torch.cuda.max_memory_reserved.return_value = 0
        for valid in (True, False):
            mapping = copy.deepcopy(self.mapping)
            if not valid:
                mapping["probabilities"]["category"]["billing"] = 0.4
            raw = json.dumps(mapping)
            operation = lambda: (raw, {"raw_generation": raw, "parsed_text_candidate": raw, "generated_token_ids": [1, 2]})
            trial = _timed_trial(torch, "cuda:0", operation, self.request, 0, output_contract="probabilities")
            self.assertEqual(trial["raw_generation"], raw)
            self.assertEqual(trial["generated_token_ids"], [1, 2])
            self.assertEqual(trial["status"], "valid" if valid else "invalid")
            if valid:
                self.assertEqual(trial["response"], self.response)
            else:
                self.assertEqual(trial["failure_category"], "schema")
                self.assertNotIn("response", trial)

    def test_cli_rejects_unknown_contract_and_existing_outputs_before_model_loading(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "existing.json"
            output.write_text("original")
            for extra in ([], ["--output-contract", "auto"]):
                with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                    main(["--request", "unused.json", "--output", str(output), *extra])
                self.assertEqual(error.exception.code, 2)
            self.assertEqual(output.read_text(), "original")


if __name__ == "__main__":
    unittest.main()
