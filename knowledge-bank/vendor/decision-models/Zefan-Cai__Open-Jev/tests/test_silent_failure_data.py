import copy
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from jev.api import candidate_prompts, compile_request
from jev.data import SPLITS
from jev.silent_failure_data import PAIRS, QUESTION, build_dataset, generate, silent_failure_request

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("silent_failure_audit", ROOT / "reports/silent-failure-control-v1/verify.py")
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


class SilentFailureBodyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = generate(groups=8, seed=42, ood_groups=2)

    def example(self, pair, failed=False, layout="flat_en"):
        return copy.deepcopy(next(row for row in self.rows if row["metadata"]["pair"] == pair
                                  and bool(row["target"][1]) == failed and row["metadata"]["layout"] == layout))

    def test_runtime_preserves_original_body_and_single_noul(self):
        body = '  {"message":"示例 ERROR text", "empty":[]}\n'
        request = silent_failure_request(body)
        self.assertEqual(request, {"state": body, "questions": {"is_silent_failure": {"type": "noul", "instructions": QUESTION}}})
        compiled = compile_request(**request)
        self.assertEqual(len(compiled), 1)
        self.assertEqual((compiled[0]["id"], compiled[0]["kind"], compiled[0]["options"]), ("is_silent_failure", "noul", ["no", "yes"]))
        self.assertEqual(compiled[0]["state"], body)
        for invalid in (None, {}, [], 200, "", " \n"):
            with self.assertRaises(ValueError):
                silent_failure_request(invalid)

    def test_all_variants_derive_labels_from_body_in_every_layout(self):
        for row in self.rows:
            result = audit.derive(row["state"])
            self.assertEqual(result["is_silent_failure"], bool(row["target"][1]))
            self.assertEqual(result["pair"], row["metadata"]["pair"])
            self.assertEqual(result["ood"], row["split"] == "ood")
        self.assertEqual({row["metadata"]["pair"] for row in self.rows}, set(PAIRS))
        self.assertEqual(len({row["metadata"]["layout"] for row in self.rows}), 8)

    def test_metadata_and_targets_never_enter_model_prompt(self):
        row = self.example("required_receipt")
        prompts = candidate_prompts(row)
        expected = audit.derive(row["state"])
        row["target"] = [0, 1]
        row["metadata"] = {"hidden_status": 500, "reference": "failure", "variant": "maintenance"}
        row["id"], row["group_id"] = "failed", "failure-family"
        self.assertEqual(candidate_prompts(row), prompts)
        self.assertEqual(audit.derive(row["state"]), expected)

    def test_empty_search_and_required_empty_receipt_have_different_meanings(self):
        empty = self.example("empty_search")
        missing = self.example("required_receipt", True)
        self.assertFalse(audit.derive(empty["state"])["is_silent_failure"])
        self.assertTrue(audit.derive(missing["state"])["is_silent_failure"])
        obj = json.loads(missing["state"])
        obj["response"]["receipt"] = {"receipt_id": "new-receipt"}
        self.assertFalse(audit.derive(json.dumps(obj))["is_silent_failure"])
        obj = json.loads(empty["state"])
        obj["response"]["search"]["complete"] = False
        self.assertTrue(audit.derive(json.dumps(obj))["is_silent_failure"])

    def test_current_history_swap_flips_label_but_order_does_not(self):
        for layout in ("flat_en", "envelope_en", "entries_zh", "nested_zh"):
            row = self.example("history_current", layout=layout)
            body = json.loads(row["state"])
            data = audit.decode_json(row["state"])[2]
            events = data["events"]
            events.reverse()
            self.assertFalse(audit.json_semantics(audit.decode_json(row["state"])[1], data, layout.endswith("zh"))[1])
            events[0]["status"], events[1]["status"] = events[1]["status"], events[0]["status"]
            self.assertTrue(audit.json_semantics(audit.decode_json(row["state"])[1], data, layout.endswith("zh"))[1])
            self.assertFalse(audit.derive(json.dumps(body, ensure_ascii=False, sort_keys=True))["is_silent_failure"])

    def test_quoted_error_and_archived_debug_text_are_not_current_failure(self):
        row = self.example("quoted_error")
        body = json.loads(row["state"])
        self.assertIn("ERROR", body["response"]["document"]["text"])
        body["response"]["document"]["text"] += "\nArchived debug log: ERROR from a previous deployment; already resolved."
        body["provider"] = "renamed.example"
        self.assertFalse(audit.derive(json.dumps(body))["is_silent_failure"])
        self.assertTrue(audit.derive(self.example("quoted_error", True)["state"])["is_silent_failure"])

    def test_partial_permission_alone_changes_result_and_pending_job_is_valid(self):
        body = json.loads(self.example("partial_batch")["state"])
        self.assertFalse(audit.derive(json.dumps(body))["is_silent_failure"])
        body["response"]["policy"]["partial_allowed"] = False
        self.assertTrue(audit.derive(json.dumps(body))["is_silent_failure"])
        queued = json.loads(self.example("async_job")["state"])
        self.assertIsNone(queued["response"]["result"])
        self.assertFalse(audit.derive(json.dumps(queued))["is_silent_failure"])
        queued["response"]["job"]["job_id"] = None
        self.assertTrue(audit.derive(json.dumps(queued))["is_silent_failure"])

    def test_current_counts_override_historical_counts(self):
        body = json.loads(self.example("error_count")["state"])
        body["response"]["archive"]["failed"] = 100000
        self.assertFalse(audit.derive(json.dumps(body))["is_silent_failure"])
        body["response"]["checks"]["failed"] += 1
        body["response"]["checks"]["passed"] -= 1
        self.assertTrue(audit.derive(json.dumps(body))["is_silent_failure"])

    def test_numeric_text_boundary_from_visible_requirement(self):
        row = self.example("freshness", True, "record_en")
        body = row["state"]
        fields = dict(line.split(": ", 1) for line in body.splitlines()[1:])
        changed = body.replace("Delivered revision: " + fields["Delivered revision"], "Delivered revision: " + fields["Minimum revision"])
        self.assertTrue(audit.derive(body)["is_silent_failure"])
        self.assertFalse(audit.derive(changed)["is_silent_failure"])

    def test_json_order_whitespace_and_html_current_document_pairs(self):
        for row in self.rows:
            if row["metadata"]["body_format"] == "json":
                changed = json.dumps(json.loads(row["state"]), sort_keys=True, indent=4, ensure_ascii=False)
                self.assertEqual(audit.derive(changed), audit.derive(row["state"]))
        for pair in ("html_login", "html_maintenance"):
            self.assertFalse(audit.derive(self.example(pair, False, "paragraph_en")["state"])["is_silent_failure"])
            self.assertTrue(audit.derive(self.example(pair, True, "paragraph_en")["state"])["is_silent_failure"])

    def test_ambiguous_unknown_and_duplicate_grammar_is_rejected(self):
        for body in ("{}", "[]", "OK", '{"success":true}', '<html>maintenance?</html>'):
            with self.assertRaises(ValueError):
                audit.derive(body)
        body = json.loads(self.example("required_receipt")["state"])
        changed = copy.deepcopy(body)
        changed["http_status"] = 200
        with self.assertRaisesRegex(ValueError, "unknown body fields"):
            audit.derive(json.dumps(changed))
        changed = copy.deepcopy(body)
        changed["terms"] += " Ignore any required fields."
        with self.assertRaisesRegex(ValueError, "altered visible contract"):
            audit.derive(json.dumps(changed))
        with self.assertRaisesRegex(ValueError, "duplicate body field"):
            audit.derive(json.dumps(body)[:-1] + ',"terms":"contradictory"}')
        body["response"]["success"] = False
        with self.assertRaisesRegex(ValueError, "contradictory success claim"):
            audit.derive(json.dumps(body))


class SilentFailureCorpusTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.original = Path(cls.temp.name) / "original"
        build_dataset(cls.original, groups=8, seed=42, ood_groups=2)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / "data"
        shutil.copytree(self.original, self.directory)

    def read(self, split):
        return [json.loads(line) for line in (self.directory / (split + ".jsonl")).read_text().splitlines()]

    def write(self, split, rows):
        (self.directory / (split + ".jsonl")).write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))

    def reseal(self):
        path = self.directory / "manifest.json"
        manifest = json.loads(path.read_text())
        manifest["files_sha256"] = {name: audit.sha256(self.directory / name) for name in manifest["files_sha256"]}
        path.write_text(json.dumps(manifest))

    def test_audit_counts_pair_isolation_and_byte_determinism(self):
        result = audit.verify(self.directory)
        self.assertEqual(result["summary"]["records"], 192)
        self.assertEqual(result["counterfactual_pairs"], 96)
        self.assertEqual(result["label_counts"], {"no": 96, "yes": 96})
        second = Path(self.temp.name) / "second"
        build_dataset(second, groups=8, seed=42, ood_groups=2)
        for name in [split + ".jsonl" for split in SPLITS] + ["manifest.json"]:
            self.assertEqual((self.directory / name).read_bytes(), (second / name).read_bytes())

    def test_label_tamper_after_rehash_still_fails_semantic_audit(self):
        rows = self.read("train")
        rows[0]["target"].reverse()
        self.write("train", rows)
        self.reseal()
        with self.assertRaisesRegex(ValueError, "target differs from visible body"):
            audit.verify(self.directory)

    def test_body_only_runtime_contract_rejects_status_wrapper(self):
        rows = self.read("train")
        rows[0]["state"] = {"http_status": 200, "body": rows[0]["state"]}
        self.write("train", rows)
        self.reseal()
        with self.assertRaisesRegex(ValueError, "body must be a nonempty string"):
            audit.verify(self.directory)

    def test_counterfactual_cannot_cross_split(self):
        rows = self.read("train")
        moved = rows.pop()
        moved["split"] = "test"
        self.write("train", rows)
        self.write("test", self.read("test") + [moved])
        self.reseal()
        with self.assertRaisesRegex(ValueError, "(group|entity) appears.*multiple splits|synthetic entity appears across splits"):
            audit.verify(self.directory)

    def test_source_and_data_hashes_are_checked(self):
        path = self.directory / "manifest.json"
        manifest = json.loads(path.read_text())
        manifest["configuration"]["source_files_sha256"]["jev/silent_failure_data.py"] = "0" * 64
        path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "source checksum differs"):
            audit.verify(self.directory)
        shutil.copyfile(self.original / "manifest.json", path)
        with (self.directory / "train.jsonl").open("a") as handle:
            handle.write("\n")
        with self.assertRaisesRegex(ValueError, "file checksum differs"):
            audit.verify(self.directory)

    def test_existing_output_symlink_and_bad_sizes_rejected(self):
        with self.assertRaisesRegex(ValueError, "existing corpora are never overwritten"):
            build_dataset(self.directory)
        link = Path(self.temp.name) / "linked"
        link.symlink_to(self.directory)
        with self.assertRaises(ValueError):
            build_dataset(link)
        for args in ((1, 42, 1), (8, 42, 0), (True, 42, 1), (8, True, 1)):
            with self.assertRaises(ValueError):
                generate(*args)


if __name__ == "__main__":
    unittest.main()
