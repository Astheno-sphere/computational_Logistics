import copy
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from jev.api import candidate_prompts, compile_request
from jev.case_email_selection import email_selection, selected_email, build_dataset, generate
from jev.data import SPLITS

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("email_control_audit", ROOT / "reports/email-selection-control-v1/verify.py")
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def line(value="MiXeD+Tag@Relay.ExAmPlE", status="current", role="Receipt destination", layout="thread"):
    return f"{role} | status={status} | email: {value}" if layout == "thread" else f"{role} :: email: {value}; status={status}"


class EmailRuntimeTest(unittest.TestCase):
    def test_current_superseded_order_and_query_blind_candidates(self):
        lines = [line("Old@relay.example", "superseded"), line("New@relay.example"), line("Bill@relay.example", role="Billing contact")]
        for sequence in (lines, list(reversed(lines))):
            text = "\n".join(sequence)
            receipt = email_selection(text, "receipt")
            billing = email_selection(text, "billing")
            self.assertEqual(receipt["state"]["candidates"], billing["state"]["candidates"])
            self.assertEqual(receipt["state"]["candidates"], audit.candidates(text))
            target = audit.selection(receipt["state"])
            self.assertEqual(selected_email(receipt, target["span"])["email"], "New@relay.example")
            for span in receipt["state"]["candidates"].values():
                self.assertEqual(text[span["start"]:span["end"]], span["text"])

    def test_superseded_only_missing_and_unrecorded_do_not_establish_current_presence(self):
        for text in (line(status="superseded"), line("not recorded"), line(""), line(role="Billing contact")):
            result = audit.selection(email_selection(text, "receipt")["state"])
            self.assertEqual((result["target_present"], result["span"], result["reason"]), (False, "none", "target_absent"))

    def test_duplicate_current_addresses_are_ambiguous_but_other_roles_are_not(self):
        address = "Same@relay.example"
        request = email_selection(line(address) + "\n" + line(address), "receipt")
        result = audit.selection(request["state"])
        self.assertEqual((result["target_present"], result["span"], result["reason"]), (True, "none", "ambiguous_target"))
        self.assertNotEqual(result["target_spans"][0]["start"], result["target_spans"][1]["start"])
        request = email_selection(line(address, role="From") + "\n" + line(address), "receipt")
        self.assertEqual(audit.selection(request["state"])["span"], "span_1")

    def test_quoted_unicode_local_and_unicode_domain_remain_present_but_unrecalled(self):
        for address in ('"Box Pair"@relay.example', "Böx@relay.example", "Box@relay.réseau.example"):
            request = email_selection(line(address), "receipt")
            ref = audit.selection(request["state"])
            self.assertEqual((ref["target_present"], ref["span"], ref["candidate_recalled"]), (True, "none", False))
            self.assertEqual(ref["reason"], "candidate_miss")
            for candidate_id in request["state"]["candidates"]:
                self.assertEqual(selected_email(request, candidate_id), audit.copied(request["state"], candidate_id))
                self.assertEqual(selected_email(request, candidate_id)["status"], "review")

    def test_copy_preserves_case_and_can_copy_wrong_role_or_superseded_contacts(self):
        text = "\n".join([line(), line("Old+TAG@Relay.ExAmPlE", "superseded"), line("Bill@Relay.ExAmPlE", role="Billing contact")])
        request = email_selection(text, "receipt")
        for candidate_id, span in request["state"]["candidates"].items():
            result = selected_email(request, candidate_id)
            self.assertEqual((result["status"], result["email"]), ("copied", span["text"]))
            self.assertEqual(result, audit.copied(request["state"], candidate_id))
        changed = copy.deepcopy(request)
        changed["state"]["requested_role"] = "intentionally-irrelevant-to-copy"
        self.assertEqual(selected_email(changed, "span_1"), selected_email(request, "span_1"))

    def test_unknown_recognized_status_rejected_in_both_layouts(self):
        for layout, role, known in (("thread", "Receipt destination", "current"), ("card", "Receipt mailbox", "active")):
            request = email_selection(line(status=known, role=role, layout=layout), "receipt", layout=layout)
            self.assertTrue(audit.selection(request["state"])["target_present"])
            with self.assertRaisesRegex(ValueError, "Unknown status"):
                email_selection(line(status="future", role=role, layout=layout), "receipt", layout=layout)
            request["state"]["text"] = line(status="future", role=role, layout=layout)
            with self.assertRaisesRegex(ValueError, "unknown status"):
                audit.fields(request["state"]["text"], request["state"]["policy"])
        ignored = email_selection(line(status="future", role="Unknown role"), "receipt")
        self.assertFalse(audit.selection(ignored["state"])["target_present"])
        self.assertEqual(selected_email(ignored, "span_0")["status"], "review")

    def test_card_offsets_and_unicode_prefix_use_original_characters(self):
        text = "Notes: résumé\n" + line("New@relay.test", "active", "Receipt mailbox", "card")
        request = email_selection(text, "receipt", layout="card")
        target = audit.selection(request["state"])["target_spans"][0]
        self.assertEqual(text[target["start"]:target["end"]], "New@relay.test")
        self.assertEqual(selected_email(request, "span_0")["email"], "New@relay.test")

    def test_no_candidates_maximum_candidates_and_corrupted_cache(self):
        empty = email_selection(line("not recorded"), "receipt")
        self.assertEqual(len(compile_request(**empty)[0]["options"]), 1)
        self.assertEqual(selected_email(empty, "none"), {"status": "no_selection", "reason": "no_candidate_selected", "email": None, "selected": None})
        with self.assertRaises(ValueError):
            selected_email(empty, "span_0")
        text = "\n".join(line(f"Box{index}@relay.example") for index in range(254))
        self.assertEqual(len(email_selection(text, "receipt")["state"]["candidates"]), 254)
        with self.assertRaisesRegex(ValueError, "More than 254"):
            email_selection(text + "\n" + line("Extra@relay.example"), "receipt")
        request = email_selection(line(), "receipt")
        request["state"]["candidates"]["span_0"]["start"] += 1
        with self.assertRaisesRegex(ValueError, "Candidate cache differs"):
            selected_email(request, "span_0")

    def test_new_original_example_recompiles_and_keeps_copy_separate(self):
        request = json.loads((ROOT / "examples/email-selection.json").read_text())
        self.assertEqual([row["id"] for row in compile_request(**request)], ["span", "target_present"])
        reference = audit.selection(request["state"])
        self.assertEqual(selected_email(request, reference["span"]), audit.copied(request["state"], reference["span"]))


class EmailCorpusAuditTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = tempfile.TemporaryDirectory()
        cls.original = Path(cls.base.name) / "original"
        build_dataset(cls.original, groups=3, seed=42, ood_groups=1)

    @classmethod
    def tearDownClass(cls):
        cls.base.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / "corpus"
        shutil.copytree(self.original, self.directory)

    def read(self, name):
        return [json.loads(value) for value in (self.directory / name).read_text().splitlines()]

    def write(self, name, values):
        (self.directory / name).write_text("".join(json.dumps(value, ensure_ascii=False) + "\n" for value in values))

    def reseal(self):
        path = self.directory / "manifest.json"
        manifest = json.loads(path.read_text())
        manifest["files_sha256"] = {name: audit.sha256(self.directory / name) for name in manifest["files_sha256"]}
        path.write_text(json.dumps(manifest))

    def test_original_counts_recall_omissions_and_deterministic_generation(self):
        result = audit.verify(self.directory)
        self.assertEqual((result["family_count"], result["document_count"], result["typed_record_count"]), (3, 42, 81))
        self.assertEqual(result["candidate_recall"]["fraction"], "15/24")
        self.assertEqual(result["candidate_copy_reference_counts"], {"copied": 255, "review": 6})
        self.assertEqual(result["omitted_supervision_counts"], {"forced_single_candidate": 3})
        self.assertEqual(generate(3, 42, 1), generate(3, 42, 1))

    def test_joint_reference_and_target_mutation_rejected(self):
        cases = self.read("cases.jsonl")
        case = cases[0]
        case["reference"]["span"] = "none"
        rows = self.read(case["split"] + ".jsonl")
        row = next(row for row in rows if row["id"] == case["id"] + ":span")
        row["target"] = [0.] * (len(row["options"]) - 1) + [1.]
        self.write("cases.jsonl", cases)
        self.write(case["split"] + ".jsonl", rows)
        self.reseal()
        with self.assertRaisesRegex(ValueError, "reference differs from visible"):
            audit.verify(self.directory)

    def test_visible_current_status_mutation_is_rejected_without_trusting_reference(self):
        cases = self.read("cases.jsonl")
        case = cases[0]
        state = case["request"]["state"]
        changed = state["text"].replace("Receipt destination | status=current", "Receipt destination | status=superseded")
        self.assertNotEqual(changed, state["text"])
        case["request"] = email_selection(changed, state["requested_role"], layout="thread")
        compiled = {row["id"]: row for row in compile_request(**case["request"])}
        rows = self.read(case["split"] + ".jsonl")
        for row in rows:
            if row["metadata"]["case_id"] == case["id"]:
                for field in ("state", "question", "kind", "options"):
                    row[field] = compiled[row["metadata"]["question_id"]][field]
        self.write("cases.jsonl", cases)
        self.write(case["split"] + ".jsonl", rows)
        self.reseal()
        with self.assertRaisesRegex(ValueError, "reference differs from visible"):
            audit.verify(self.directory)

    def test_candidate_copy_cannot_silently_lowercase_addresses(self):
        cases = self.read("cases.jsonl")
        copy_result = cases[0]["candidate_copy_references"][0]["result"]
        copy_result["email"] = copy_result["email"].lower()
        self.write("cases.jsonl", cases)
        self.reseal()
        with self.assertRaisesRegex(ValueError, "candidate copy reference differs"):
            audit.verify(self.directory)

    def test_groups_and_contact_identity_are_isolated(self):
        initial = self.read("cases.jsonl")
        cases = copy.deepcopy(initial)
        cases[0]["split"] = "test" if cases[0]["split"] != "test" else "train"
        self.write("cases.jsonl", cases)
        self.reseal()
        with self.assertRaisesRegex(ValueError, "family linkage differs"):
            audit.verify(self.directory)
        cases = copy.deepcopy(initial)
        other = next(case for case in cases if case["family_id"] != cases[0]["family_id"])
        first_text = cases[0]["request"]["state"]["text"]
        code = first_text.split("\n", 1)[0].split()[-1].split("-")[0]
        text = other["request"]["state"]["text"]
        old_code = text.split("\n", 1)[0].split()[-1].split("-")[0]
        other["request"]["state"]["text"] = text.replace(old_code, code, 1)
        self.write("cases.jsonl", cases)
        self.reseal()
        with self.assertRaisesRegex(ValueError, "contact identity crosses family groups"):
            audit.verify(self.directory)

    def test_source_hash_binding_and_unsealed_bytes_are_checked(self):
        path = self.directory / "manifest.json"
        initial = path.read_text()
        manifest = json.loads(initial)
        manifest["configuration"]["source_files_sha256"]["case_email_selection.py"] = "0" * 64
        path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "generator/runtime source hashes differ"):
            audit.verify(self.directory)
        path.write_text(initial)
        with (self.directory / "families.jsonl").open("a") as stream:
            stream.write("\n")
        with self.assertRaisesRegex(ValueError, "manifest file hashes differ"):
            audit.verify(self.directory)

    def test_hidden_reference_and_ids_do_not_enter_prompts(self):
        _, _, rows = generate(2, 42, 1)
        for row in rows:
            before = candidate_prompts(row)
            changed = copy.deepcopy(row)
            changed.update(id="HIDDEN", target=[.5, .5], metadata={"reference": "HIDDEN"}, split="HIDDEN")
            self.assertEqual(candidate_prompts(changed), before)
            self.assertEqual(set(row["state"]), {"text", "requested_role", "policy", "candidates"})

    def test_build_does_not_overwrite_existing_corpus(self):
        before = audit.sha256(self.directory / "manifest.json")
        with self.assertRaisesRegex(ValueError, "existing corpora are never overwritten"):
            build_dataset(self.directory, 3, 42, 1)
        self.assertEqual(audit.sha256(self.directory / "manifest.json"), before)

    def test_output_rejects_input_paths_aliases_existing_files_and_symlinks(self):
        alias = Path(self.temp.name) / "alias"
        alias.symlink_to(self.directory, target_is_directory=True)
        existing = Path(self.temp.name) / "previous.json"
        existing.write_text("preserve")
        linked = Path(self.temp.name) / "linked.json"
        linked.symlink_to(existing)
        dangling = Path(self.temp.name) / "dangling.json"
        dangling.symlink_to(Path(self.temp.name) / "absent.json")
        before = {path.name: path.read_bytes() for path in self.directory.iterdir()}
        for output in (self.directory / "manifest.json", self.directory / "train.jsonl", alias / "new.json", existing, linked, dangling):
            with self.subTest(output=output), patch.object(audit, "verify", side_effect=AssertionError("must reject before reading")):
                with self.assertRaisesRegex(ValueError, "outside the input|already exists|must not be a symlink"):
                    audit.main(["--data", str(self.directory), "--output", str(output)])
        self.assertEqual(existing.read_text(), "preserve")
        self.assertEqual({path.name: path.read_bytes() for path in self.directory.iterdir()}, before)

    def test_output_exclusive_creation_preserves_concurrent_file(self):
        output = Path(self.temp.name) / "audit.json"
        with redirect_stdout(io.StringIO()):
            self.assertEqual(audit.main(["--data", str(self.directory), "--output", str(output)]), 0)
        self.assertTrue(json.loads(output.read_text())["verified"])
        output.unlink()
        original = audit.verify

        def concurrent(directory):
            result = original(directory)
            output.write_text("concurrent")
            return result

        with patch.object(audit, "verify", side_effect=concurrent), self.assertRaises(FileExistsError):
            audit.main(["--data", str(self.directory), "--output", str(output)])
        self.assertEqual(output.read_text(), "concurrent")


if __name__ == "__main__":
    unittest.main()
