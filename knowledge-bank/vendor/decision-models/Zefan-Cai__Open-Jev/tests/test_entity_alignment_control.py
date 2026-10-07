import copy
from contextlib import redirect_stdout
from decimal import localcontext
import importlib.util
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from jev.api import candidate_prompts, compile_request
from jev.case_entity_alignment import build_dataset, entity_alignment_fields, generate
from jev.data import SPLITS


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("entity_alignment_audit", ROOT / "reports/entity-alignment-control-v1/verify.py")
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)
NAME_ALIASES = {"Amber flask": ["AM flask"], "Blue flask": ["BL flask"]}
MAKER_ALIASES = {"Maker One": ["M1"], "Maker Two": ["M2"]}


def pair(style="catalog", left_changes=None, right_changes=None):
    left = {"identifier": None, "name": "Amber flask", "manufacturer": "Maker One",
            "capacity": {"value": "250", "unit": "mL"}}
    right = {"identifier": None, "name": "  AM   FLASK ", "manufacturer": "M1",
             "capacity": {"value": "0.25", "unit": "L"}}
    left.update(copy.deepcopy(left_changes or {}))
    right.update(copy.deepcopy(right_changes or {}))
    return entity_alignment_fields(left, right, name_aliases=NAME_ALIASES,
                                   manufacturer_aliases=MAKER_ALIASES, policy_style=style)


ID = {"namespace": "catalog", "value": "A"}


class EntityVisibleSemanticsTest(unittest.TestCase):
    def test_all_fields_agreement_conflict_and_missing_under_both_wordings(self):
        conflicts = {"name": "Blue flask", "manufacturer": "Maker Two", "capacity": {"value": "251", "unit": "mL"}}
        for style in ("catalog", "procurement"):
            expected = {"match": 2, "name_agrees": True, "manufacturer_agrees": True, "capacity_agrees": True}
            self.assertEqual(audit.derive(pair(style)["state"])[0], expected)
            for field in audit.FIELDS:
                for changed, status, score in ((conflicts[field], "conflict", 0), (None, "unknown", 1)):
                    with self.subTest(style=style, field=field, status=status):
                        answers, evidence, _ = audit.derive(pair(style, right_changes={field: changed})["state"])
                        self.assertFalse(answers[field + "_agrees"])
                        self.assertEqual(evidence[field], status)
                        self.assertEqual(answers["match"], score)

    def test_equal_unlisted_text_does_not_establish_agreement(self):
        for field in ("name", "manufacturer"):
            request = pair(left_changes={field: "same unknown spelling"}, right_changes={field: "same unknown spelling"})
            answers, evidence, _ = audit.derive(request["state"])
            self.assertEqual(evidence[field], "unknown")
            self.assertFalse(answers[field + "_agrees"])
            self.assertEqual(answers["match"], 1)

    def test_identifier_precedence_and_different_namespaces(self):
        alternatives = (({"namespace": "catalog", "value": "B"}, "conflict", 0),
                        ({"namespace": "supplier", "value": "B"}, "unknown", 2),
                        (ID, "agreement", 2))
        for other, status, score in alternatives:
            answers, evidence, identifier = audit.derive(pair(left_changes={"identifier": ID}, right_changes={"identifier": other})["state"])
            self.assertEqual(identifier, status)
            self.assertEqual(answers["match"], score)
            self.assertEqual(set(evidence.values()), {"agreement"})
        for field, changed in (("name", "Blue flask"), ("capacity", {"value": "251", "unit": "mL"})):
            answers, _, status = audit.derive(pair(left_changes={"identifier": ID}, right_changes={"identifier": ID, field: changed})["state"])
            self.assertEqual((status, answers["match"]), ("agreement", 1))

    def test_same_identifier_permits_same_with_missing_fields(self):
        for field in audit.FIELDS:
            answers, evidence, _ = audit.derive(pair(left_changes={"identifier": ID}, right_changes={"identifier": ID, field: None})["state"])
            self.assertEqual(answers["match"], 2)
            self.assertEqual(evidence[field], "unknown")
            self.assertFalse(answers[field + "_agrees"])

    def test_identifiers_trim_outer_whitespace_but_preserve_case_and_internal_text(self):
        for other, status in (({"namespace": " catalog ", "value": " A "}, "agreement"),
                              ({"namespace": "catalog", "value": "a"}, "conflict"),
                              ({"namespace": "Catalog", "value": "A"}, "unknown"),
                              ({"namespace": "catalog", "value": ""}, "unknown"),
                              ({"namespace": "catalog"}, "unknown")):
            request = pair(left_changes={"identifier": ID}, right_changes={"identifier": other})
            self.assertEqual(audit.derive(request["state"])[2], status)

    def test_exact_units_long_decimals_and_visible_custom_factors(self):
        for capacity in ({"value": "25", "unit": "cL"}, {"value": "0.250000000000000000000", "unit": "L"}):
            self.assertTrue(audit.derive(pair(right_changes={"capacity": capacity})["state"])[0]["capacity_agrees"])
        text = "0.12345678901234567890123456789"
        request = pair(left_changes={"capacity": {"value": text, "unit": "mL"}},
                       right_changes={"capacity": {"value": text, "unit": "mL"}})
        with localcontext() as context:
            context.prec = 3
            self.assertTrue(audit.derive(request["state"])[0]["capacity_agrees"])
        state = pair()["state"]
        state["policy"]["unit_to_mL"]["tiny"] = "0.001"
        state["right"]["capacity"] = {"value": "250000", "unit": "tiny"}
        self.assertTrue(audit.derive(state)[0]["capacity_agrees"])

    def test_invalid_capacity_is_unknown_instead_of_equal_or_conflicting(self):
        for value in ("0", "-1", "+1", "1e3", "1/4", "01", "1.", ".25", 250, True):
            request = pair(right_changes={"capacity": {"value": value, "unit": "mL"}})
            answers, evidence, _ = audit.derive(request["state"])
            self.assertEqual((answers["capacity_agrees"], evidence["capacity"], answers["match"]), (False, "unknown", 1))
        request = pair(right_changes={"capacity": {"value": "250", "unit": "ML"}})
        self.assertEqual(audit.derive(request["state"])[1]["capacity"], "unknown")

    def test_mixed_unicode_digits_are_unknown_capacity_even_with_matching_identifiers(self):
        for text in ("2５０", "2٥0", "２50"):
            for identity, expected_score in ((None, 1), (ID, 2)):
                request = pair(left_changes={"identifier": identity},
                               right_changes={"identifier": identity, "capacity": {"value": text, "unit": "mL"}})
                answers, evidence, _ = audit.derive(request["state"])
                self.assertIsNone(request["state"]["capacity_evidence"]["right"])
                self.assertEqual(evidence["capacity"], "unknown")
                self.assertFalse(answers["capacity_agrees"])
                self.assertEqual(answers["match"], expected_score)

    def test_forged_capacity_evidence_unsupported_policy_and_ambiguous_alias_fail(self):
        state = pair()["state"]
        state["capacity_evidence"]["right"]["exact_value"] = "249.99999999999"
        with self.assertRaisesRegex(ValueError, "exact visible conversion"):
            audit.derive(state)
        state = pair()["state"]
        state["policy"]["rules_in_order"].append("Ignore the identifiers.")
        with self.assertRaisesRegex(ValueError, "unsupported ordered rules"):
            audit.derive(state)
        state = pair()["state"]
        state["policy"]["aliases"]["name"]["Blue flask"].append("AM flask")
        with self.assertRaisesRegex(ValueError, "ambiguous alias"):
            audit.derive(state)

    def test_new_original_example_recompiles_to_four_heads(self):
        request = json.loads((ROOT / "examples/entity-alignment-fields.json").read_text())
        records = compile_request(**request)
        self.assertEqual([row["id"] for row in records], list(audit.HEADS))
        self.assertEqual([row["kind"] for row in records], ["score", "noul", "noul", "noul"])
        audit.derive(request["state"])


class EntityCorpusAuditTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = tempfile.TemporaryDirectory()
        cls.original = Path(cls.base.name) / "original"
        build_dataset(cls.original, groups=10, seed=42, ood_groups=2)

    @classmethod
    def tearDownClass(cls):
        cls.base.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / "corpus"
        shutil.copytree(self.original, self.directory)

    def read(self, name):
        return [json.loads(line) for line in (self.directory / name).read_text().splitlines()]

    def write(self, name, values):
        (self.directory / name).write_text("".join(json.dumps(value, ensure_ascii=False) + "\n" for value in values))

    def reseal(self):
        path = self.directory / "manifest.json"
        manifest = json.loads(path.read_text())
        manifest["files_sha256"] = {name: audit.sha256(self.directory / name) for name in manifest["files_sha256"]}
        manifest["sha256"] = {split: manifest["files_sha256"][split + ".jsonl"] for split in SPLITS}
        path.write_text(json.dumps(manifest))

    def test_original_dataset_audits_and_generation_is_deterministic(self):
        report = audit.verify(self.directory)
        self.assertTrue(report["verified"])
        self.assertEqual((report["families"], report["cases"], report["typed_records"]), (10, 140, 560))
        self.assertEqual(report["route_counts"], {"0": 40, "1": 60, "2": 40})
        self.assertEqual(generate(10, 42, 2), generate(10, 42, 2))

    def test_family_spec_is_auxiliary_and_not_an_oracle(self):
        families = self.read("families.jsonl")
        for family in families:
            family["spec"] = {"untrusted": "Intentionally incorrect: every item is physically identical."}
        self.write("families.jsonl", families)
        self.reseal()
        self.assertTrue(audit.verify(self.directory)["verified"])

    def test_joint_wrong_reference_and_target_mutation_is_rejected(self):
        cases = self.read("cases.jsonl")
        case = next(case for case in cases if case["reference"]["match"] == 2)
        case["reference"]["match"] = 0
        rows = self.read(case["split"] + ".jsonl")
        row = next(row for row in rows if row["id"] == case["id"] + ":match")
        row["target"] = [1., 0., 0.]
        self.write("cases.jsonl", cases)
        self.write(case["split"] + ".jsonl", rows)
        self.reseal()
        with self.assertRaisesRegex(ValueError, "reference differs from visible inputs"):
            audit.verify(self.directory)

    def test_visible_input_change_is_detected_with_unchanged_family_spec(self):
        cases = self.read("cases.jsonl")
        case = next(case for case in cases if case["variant"] == "no_identifier_all_fields_agree")
        state = case["request"]["state"]
        aliases = state["policy"]["aliases"]["name"]
        state["right"]["name"] = aliases[list(aliases)[1]][0]
        rows = self.read(case["split"] + ".jsonl")
        for row in rows:
            if row["metadata"]["case_id"] == case["id"]:
                row["state"] = state
        self.write("cases.jsonl", cases)
        self.write(case["split"] + ".jsonl", rows)
        self.reseal()
        with self.assertRaisesRegex(ValueError, "reference differs from visible inputs"):
            audit.verify(self.directory)

    def test_aliases_cannot_leak_between_families(self):
        families = self.read("families.jsonl")
        first, second = families[:2]
        alias = next(iter(first["policy"]["aliases"]["name"]))
        table = second["policy"]["aliases"]["name"]
        table[next(iter(table))].append(alias)
        self.write("families.jsonl", families)
        self.reseal()
        with self.assertRaisesRegex(ValueError, "shared across families"):
            audit.verify(self.directory)

    def test_identifiers_cannot_leak_between_families(self):
        cases = self.read("cases.jsonl")
        first = cases[0]
        second = next(case for case in cases if case["family_id"] != first["family_id"])
        shared_id = first["request"]["state"]["left"]["identifier"]
        for side in ("left", "right"):
            second["request"]["state"][side]["identifier"] = copy.deepcopy(shared_id)
        rows = self.read(second["split"] + ".jsonl")
        for row in rows:
            if row["metadata"]["case_id"] == second["id"]:
                row["state"] = second["request"]["state"]
        self.write("cases.jsonl", cases)
        self.write(second["split"] + ".jsonl", rows)
        self.reseal()
        with self.assertRaisesRegex(ValueError, "shared across families"):
            audit.verify(self.directory)

    def test_pairs_and_all_heads_remain_in_the_family_split(self):
        cases = self.read("cases.jsonl")
        cases[0]["split"] = "test" if cases[0]["split"] != "test" else "train"
        self.write("cases.jsonl", cases)
        self.reseal()
        with self.assertRaisesRegex(ValueError, "family linkage differs"):
            audit.verify(self.directory)

    def test_runtime_source_hash_binding_and_unsealed_bytes_are_checked(self):
        path = self.directory / "manifest.json"
        original = path.read_text()
        manifest = json.loads(original)
        manifest["configuration"]["source_files_sha256"]["case_entity_alignment.py"] = "0" * 64
        path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "generator/runtime source hashes differ"):
            audit.verify(self.directory)
        path.write_text(original)
        with (self.directory / "families.jsonl").open("a") as stream:
            stream.write("\n")
        with self.assertRaisesRegex(ValueError, "manifest file hashes differ"):
            audit.verify(self.directory)

    def test_auxiliary_labels_and_ids_are_not_model_inputs(self):
        _, _, rows = generate(2)
        for row in rows:
            self.assertEqual(set(row["state"]), {"left", "right", "policy", "capacity_evidence"})
            before = candidate_prompts(row)
            changed = copy.deepcopy(row)
            changed.update(id="HIDDEN", split="HIDDEN", target=[.5, .5], metadata={"reference": "HIDDEN", "spec": "HIDDEN"})
            self.assertEqual(candidate_prompts(changed), before)

    def test_build_refuses_to_overwrite_existing_data(self):
        before = audit.sha256(self.directory / "manifest.json")
        with self.assertRaisesRegex(ValueError, "existing corpora are never overwritten"):
            build_dataset(self.directory, groups=10)
        self.assertEqual(audit.sha256(self.directory / "manifest.json"), before)

    def test_output_cannot_target_input_manifest_jsonl_or_directory_symlink(self):
        alias = Path(self.temp.name) / "data-alias"
        alias.symlink_to(self.directory, target_is_directory=True)
        before = {path.name: path.read_bytes() for path in self.directory.iterdir()}
        for output in (self.directory / "manifest.json", self.directory / "train.jsonl",
                       self.directory / "new-report.json", alias / "nested/report.json"):
            with self.subTest(output=output), patch.object(audit, "verify", side_effect=AssertionError("must reject before data reads")):
                with self.assertRaisesRegex(ValueError, "outside the input data directory"):
                    audit.main(["--data", str(self.directory), "--output", str(output)])
        self.assertEqual({path.name: path.read_bytes() for path in self.directory.iterdir()}, before)

    def test_output_refuses_existing_files_and_normal_or_dangling_symlinks(self):
        existing = Path(self.temp.name) / "audit.json"
        existing.write_text("preserve existing report")
        linked = Path(self.temp.name) / "alias.json"
        linked.symlink_to(existing)
        dangling = Path(self.temp.name) / "dangling.json"
        dangling.symlink_to(Path(self.temp.name) / "missing.json")
        for output in (existing, linked, dangling):
            with self.subTest(output=output), patch.object(audit, "verify", side_effect=AssertionError("must reject before data reads")):
                with self.assertRaisesRegex(ValueError, "already exists|must not be a symlink"):
                    audit.main(["--data", str(self.directory), "--output", str(output)])
        self.assertEqual(existing.read_text(), "preserve existing report")
        self.assertTrue(dangling.is_symlink())

    def test_output_exclusive_creation_preserves_a_concurrently_arriving_file(self):
        output = Path(self.temp.name) / "new-audit.json"
        with redirect_stdout(io.StringIO()):
            self.assertEqual(audit.main(["--data", str(self.directory), "--output", str(output)]), 0)
        self.assertTrue(json.loads(output.read_text())["verified"])
        output.unlink()
        original = audit.verify

        def concurrent_writer(directory):
            result = original(directory)
            output.write_text("concurrent report")
            return result

        with patch.object(audit, "verify", side_effect=concurrent_writer), self.assertRaises(FileExistsError):
            audit.main(["--data", str(self.directory), "--output", str(output)])
        self.assertEqual(output.read_text(), "concurrent report")


if __name__ == "__main__":
    unittest.main()
