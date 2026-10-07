import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from jev.api import compile_request
from jev.eval_frontier import (SOURCE_COMMIT, SOURCE_FILES, audit_outcomes,
                               bootstrap_pair_means, build_request, digest,
                               load_benchmark, paired_comparison, presented_gold,
                               presented_options, summarize, task_order,
                               validate_choice_response, validate_items)


def items():
    result = []
    for domain in ("domain_one", "domain_two"):
        for variant in ("a", "b"):
            result.append({"id": domain + ":" + variant, "pair_id": domain + ":pair", "domain": domain,
                           "difficulty": "easy", "state": f"Synthetic {domain} observation {variant}",
                           "question": "Which option is supported?", "options": {"A": "alpha", "B": "beta", "C": "gamma", "D": "delta"},
                           "answer": "C" if variant == "a" else "D", "rationale": "Never include this rationale in an input."})
    return result


def outcomes(dataset, correct=True):
    result = []
    for item, trial in task_order(dataset):
        gold = presented_gold(item, trial)
        answer = gold if correct else next(value for value in "ABCD" if value != gold)
        result.append({"item_id": item["id"], "trial": trial, "domain": item["domain"], "difficulty": item["difficulty"],
                       "pair_id": item["pair_id"], "gold": gold, "answer": answer, "status": "ok", "correct": correct,
                       "elapsed_ms": 5, "request_sha256": digest(build_request(item, trial, "test-model"))})
    return result


class FrontierProtocolTests(unittest.TestCase):
    def test_native_choice_rotation_preserves_meaning_and_remaps_gold(self):
        item = items()[0]
        self.assertEqual([presented_gold(item, trial) for trial in range(3)], ["C", "B", "A"])
        for trial in range(3):
            request = build_request(item, trial)
            self.assertEqual(set(request), {"state", "questions", "model"})
            self.assertEqual(set(request["questions"]), {"answer"})
            self.assertEqual(presented_options(item, trial)[presented_gold(item, trial)], item["options"][item["answer"]])
            self.assertEqual(compile_request(request["state"], request["questions"])[0]["kind"], "choice")
        self.assertEqual(list(presented_options(item, 1).values()), ["beta", "gamma", "delta", "alpha"])
        with self.assertRaises(ValueError):
            build_request(item, 3)

    def test_request_builder_never_reads_gold_rationale_or_other_hidden_metadata(self):
        item = items()[0]
        expected = build_request(item, 0)
        item.update(answer=object(), rationale=object(), difficulty=object(), oracle=object(), pair_id=object(), domain=object())
        self.assertEqual(build_request(item, 0), expected)
        text = json.dumps(expected)
        self.assertNotIn("rationale", text)
        self.assertNotIn("difficulty", text)
        self.assertNotIn("Never include", text)
        self.assertNotIn("seed", expected)

    def test_request_hash_matches_upstream_json_normalization(self):
        import hashlib
        request = build_request(items()[0], 2, "jev-1.13.0")
        self.assertEqual(digest(request), hashlib.sha256(json.dumps(request, sort_keys=True, ensure_ascii=False).encode()).hexdigest())
        self.assertNotEqual(digest(request), digest(build_request(items()[0], 2, "open-jev")))

    def test_audit_requires_all_trials_correct_rotated_gold_and_request_identity(self):
        dataset = items()
        rows = outcomes(dataset)
        audit_outcomes(rows, dataset, expected_model="test-model")
        for mutation in (lambda values: values.pop(), lambda values: values.append(copy.deepcopy(values[0])),
                         lambda values: values[0].update(gold="invalid"), lambda values: values[0].update(correct=False),
                         lambda values: values[0].update(request_sha256="wrong"), lambda values: values[0].update(pair_id="wrong")):
            changed = copy.deepcopy(rows)
            mutation(changed)
            with self.assertRaises(ValueError):
                audit_outcomes(changed, dataset, expected_model="test-model")
        duplicate_pair = copy.deepcopy(dataset)
        duplicate_pair[1]["domain"] = "wrong-domain"
        with self.assertRaises(ValueError):
            validate_items(duplicate_pair)

    def test_statistics_keep_template_pairs_and_score_service_failures_zero(self):
        dataset = items()
        rows = outcomes(dataset)
        summary = summarize(rows, dataset, draws=100)
        self.assertEqual(summary["accuracy"], 1.0)
        self.assertEqual(summary["accuracy_95ci"], [1.0, 1.0])
        self.assertEqual(summary["semantic_consistency"], 1.0)
        self.assertEqual(summary["pair_joint_accuracy"], 1.0)
        failed = copy.deepcopy(rows)
        failed[0].update(status="service_error", answer=None, correct=False)
        stats = summarize(failed, dataset, draws=100)
        self.assertEqual(stats["correct"], 11)
        self.assertEqual(stats["valid_completion_rate"], 11 / 12)
        self.assertEqual(stats["accuracy_among_valid"], 1)
        self.assertEqual(stats["consistency_eligible_items"], 3)
        comparison = paired_comparison(summary, summarize(outcomes(dataset, correct=False), dataset, draws=100), draws=100)
        self.assertEqual(comparison["difference"], 1.0)
        self.assertEqual(comparison["95ci"], [1.0, 1.0])
        self.assertEqual(comparison["pairs"], 2)

    def test_native_probability_validation_catches_invalid_answers_without_retry(self):
        response = {"answers": {"answer": {"type": "choice", "choice": "C", "probabilities": {"A": 0.1, "B": 0.2, "C": 0.5, "D": 0.2}}}}
        self.assertEqual(validate_choice_response(response), "C")
        for mutate in (lambda r: r["answers"].update(other={}), lambda r: r["answers"]["answer"].update(choice="A"),
                       lambda r: r["answers"]["answer"]["probabilities"].update(C=float("nan")),
                       lambda r: r["answers"]["answer"]["probabilities"].update(C=0.4)):
            changed = copy.deepcopy(response)
            mutate(changed)
            with self.assertRaises(ValueError):
                validate_choice_response(changed)

    def test_checksum_or_source_commit_change_is_rejected_before_loading_items(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            with patch("jev.eval_frontier.subprocess.check_output", return_value="wrong-commit\n"):
                with self.assertRaisesRegex(ValueError, "pinned"):
                    load_benchmark(source)
            (source / "data").mkdir()
            (source / "data/items.jsonl").write_text("modified dataset\n")
            with patch("jev.eval_frontier.subprocess.check_output", return_value=SOURCE_COMMIT + "\n"):
                with self.assertRaisesRegex(ValueError, "checksum"):
                    load_benchmark(source)


_source = Path(os.environ.get("JF100_SOURCE", "/path/to/developer/Codex-new/jev-source-research/jev-frontier-100"))


@unittest.skipUnless((_source / "data/items.jsonl").exists(), "requires external pinned JF100 checkout")
class FrontierFrozenSourceTests(unittest.TestCase):
    def test_all_300_published_request_hashes_and_reference_statistics_reproduce(self):
        dataset, reference, published, provenance = load_benchmark(_source)
        self.assertEqual(len(dataset), 100)
        self.assertEqual(len(reference), 300)
        self.assertEqual(provenance["files_sha256"]["data/items.jsonl"], SOURCE_FILES["data/items.jsonl"])
        recomputed = summarize(reference, dataset)
        for field in ("correct", "accuracy", "accuracy_95ci", "pair_joint_accuracy", "semantic_consistency", "groups"):
            self.assertEqual(recomputed[field], published[field], field)
        self.assertEqual(recomputed["correct"], 231)
        self.assertEqual(recomputed["accuracy"], 0.77)


if __name__ == "__main__":
    unittest.main()
