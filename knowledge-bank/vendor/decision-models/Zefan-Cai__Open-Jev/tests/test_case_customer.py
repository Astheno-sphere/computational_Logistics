import json
import random
from pathlib import Path
import tempfile
import unittest

from jev.api import compile_request, format_response
from jev.case_customer import (UTTERANCES, build_dataset, generate_cases,
                               _dialogue, latent_targets, question_definitions)
from jev.data import SPLITS, read_jsonl, validate_records


class CustomerCaseTests(unittest.TestCase):
    def test_source_question_forms_and_independent_score_descriptions(self):
        questions = question_definitions()
        self.assertEqual({key: value["type"] for key, value in questions.items()}, {
            "category": "choice", "bug_severity": "score", "has_reproducible_steps": "noul",
            "refund_requested": "noul", "frustration": "score", "churn_likelihood_level": "score"})
        self.assertEqual(set(questions["category"]["criteria"]), {"bug_report", "billing", "feature_request", "account"})
        for definition in questions.values():
            if definition["type"] == "score":
                self.assertTrue(all(len(text.split()) >= 2 for text in definition["criteria"]))

    def test_latent_marginal_is_defined_not_a_guessed_confidence(self):
        control = {"categories": ["billing", "account"], "ambiguity": "category", "severity": 0,
                   "repro": False, "refund": True, "frustration": 1, "churn": 2}
        target = latent_targets(control)
        self.assertEqual(target["category"], {"bug_report": 0.0, "billing": 0.5, "feature_request": 0.0, "account": 0.5})
        control["ambiguity"] = "churn_likelihood_level"
        self.assertEqual(latent_targets(control)["churn_likelihood_level"], [1 / 3] * 3)
        self.assertEqual(target["refund_requested"], [0.0, 1.0])

    def test_hidden_worlds_with_identical_observations_have_identical_targets(self):
        base = {"categories": ["bug_report"], "severity": 1, "repro": True,
                "refund": False, "frustration": 0, "churn": 0}
        for ambiguity, latent, worlds in (("bug_severity", "severity", [1, 2]),
                                          ("frustration", "frustration", [0, 1]),
                                          ("churn_likelihood_level", "churn", [0, 1, 2])):
            for ood in (False, True):
                observed = []
                targets = []
                for world in worlds:
                    control = dict(base, ambiguity=ambiguity)
                    control[latent] = world
                    observed.append(_dialogue(control, random.Random(23), "shared-account", ood, True, 0))
                    targets.append(latent_targets(control))
                self.assertTrue(all(state == observed[0] for state in observed))
                self.assertTrue(all(target == targets[0] for target in targets))

    def test_workflows_compile_to_the_training_inputs_and_targets(self):
        cases = list(generate_cases(150, 13))
        self.assertEqual(cases, list(generate_cases(150, 13)))
        for workflow, rows in cases:
            compiled = compile_request(workflow["state"], workflow["questions"])
            self.assertEqual(len(compiled), 6)
            for item, row in zip(compiled, rows):
                self.assertEqual([item[key] for key in ("state", "question", "kind", "options")],
                                 [row[key] for key in ("state", "question", "kind", "options")])
                self.assertEqual(row["target"], workflow["targets"][item["id"]])
                self.assertEqual(row["metadata"]["provenance"]["annotation_status"], "synthetic_control_not_official_labels")
                self.assertNotIn("control_latents", workflow["state"])
                self.assertNotIn("target", item)
            response = format_response(compiled, [workflow["targets"][r["id"]] for r in compiled])
            self.assertEqual(len(response["answers"]), 6)
        self.assertEqual(validate_records(row for _, rows in cases for row in rows)["groups"], 150)

    def test_ood_full_utterances_and_templates_are_reserved(self):
        def texts(bank):
            return {item for value in bank.values() for item in (value if isinstance(value, list) else [value])}
        self.assertFalse(texts(UTTERANCES["id"]) & texts(UTTERANCES["ood"]))
        instructions = json.dumps(question_definitions())
        self.assertTrue(all(text not in instructions for text in texts(UTTERANCES["ood"])))
        templates = {False: set(), True: set()}
        bilingual = False
        for workflow, rows in generate_cases(200):
            templates[workflow["split"] == "ood"].add(rows[0]["metadata"]["template_id"])
            bilingual |= rows[0]["metadata"]["language"] == "en+zh"
        self.assertFalse(templates[False] & templates[True])
        self.assertTrue(bilingual)

    def test_cosmetic_reproduction_does_not_describe_broken_functionality(self):
        found = False
        for workflow, rows in generate_cases(300):
            control = rows[0]["metadata"]["control_latents"]
            if "bug_report" in control["categories"] and control["severity"] == 0 and control["repro"]:
                found = True
                self.assertNotIn("nothing is saved", workflow["state"])
                self.assertNotIn("without creating a file", workflow["state"])
                self.assertEqual(workflow["targets"]["bug_severity"], [1.0, 0.0, 0.0])
        self.assertTrue(found)

    def test_saved_workflow_choice_order_roundtrip(self):
        with tempfile.TemporaryDirectory() as temporary:
            manifest = build_dataset(temporary, groups=80, seed=42)
            self.assertEqual(manifest["summary"]["records"], 480)
            rows = [row for split in SPLITS for row in read_jsonl(Path(temporary) / f"{split}.jsonl")]
            validate_records(rows)
            by_id = {row["id"]: row for row in rows}
            for line in (Path(temporary) / "workflow_cases.jsonl").read_text().splitlines():
                workflow = json.loads(line)
                for item in compile_request(workflow["state"], workflow["questions"]):
                    row = by_id[workflow["group_id"] + ":" + item["id"]]
                    self.assertEqual(item["options"], row["options"])
                    self.assertEqual(workflow["targets"][item["id"]], row["target"])


if __name__ == "__main__":
    unittest.main()
