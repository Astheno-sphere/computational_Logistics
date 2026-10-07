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
from jev.case_amount_extraction import amount_selection, amount_attributes, normalize_amount, build_dataset, generate
from jev.data import SPLITS

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("amount_control_audit", ROOT / "reports/amount-extraction-control-v1/verify.py")
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def document(value="USD 12.34", flow="charge", *, locale="US", layout="invoice", declaration="USD", extras=()):
    line = f"Amount due: {value} | Flow: {flow}" if layout == "invoice" else f"Payable now :: flow={flow}; value={value}"
    return "\n".join(["Invoice handwritten", f"Number format: {locale}", f"Currency declaration: {declaration}", *extras, line])


def request(value="USD 12.34", flow="charge", **kwargs):
    return amount_selection(document(value, flow, **kwargs), "due", locale=kwargs.get("locale", "US"), layout=kwargs.get("layout", "invoice"))


def actual_attributes(selection, candidate_id=None):
    candidate_id = candidate_id or next(iter(selection["state"]["candidates"]))
    return amount_attributes(selection, candidate_id)


class AmountRuntimeTest(unittest.TestCase):
    def test_candidates_are_query_blind_and_preserve_original_character_offsets(self):
        text = document(extras=("Memo: résumé USD 1.00", "Tax: USD 2.00 | Flow: charge"))
        due = amount_selection(text, "due", locale="US")
        tax = amount_selection(text, "tax", locale="US")
        self.assertEqual(due["state"]["candidates"], tax["state"]["candidates"])
        self.assertEqual(due["state"]["candidates"], audit.candidates(text))
        for span in due["state"]["candidates"].values():
            self.assertEqual(text[span["start"]:span["end"]], span["text"])
        self.assertNotEqual(audit.selection(due["state"])["span"], audit.selection(tax["state"])["span"])
        outside_field = actual_attributes(due, "span_0")
        self.assertFalse(audit.attributes(outside_field["state"])["complete_field"])

    def test_absent_unsupported_and_unrecalled_populated_fields_remain_distinct(self):
        for value, locale, reason, present in (("not recorded", "US", "target_absent", False),
                                               ("nonsense", "US", "candidate_miss", True),
                                               ("EUR 1\u202f234,56", "EU", "candidate_miss", True),
                                               ("(USD 12.34)", "US", "candidate_miss", True)):
            result = audit.selection(request(value, locale=locale)["state"])
            self.assertEqual((result["reason"], result["target_present"], result["span"]), (reason, present, "none"))
        text = "Number format: US\nCurrency declaration: USD\nTax: USD 1.00 | Flow: charge"
        self.assertFalse(audit.selection(amount_selection(text, "due", locale="US")["state"])["target_present"])

    def test_same_value_different_offsets_and_duplicate_target_roles(self):
        text = document(extras=("Subtotal: USD 12.34 | Flow: charge",))
        selected = amount_selection(text, "due", locale="US")
        ref = audit.selection(selected["state"])
        self.assertEqual(ref["span"], "span_1")
        self.assertEqual(selected["state"]["candidates"]["span_0"]["text"], selected["state"]["candidates"]["span_1"]["text"])
        duplicate = amount_selection(text + "\nAmount due: USD 12.34 | Flow: charge", "due", locale="US")
        ref = audit.selection(duplicate["state"])
        self.assertEqual((ref["reason"], ref["span"], ref["candidate_recalled"]), ("ambiguous_target", "none", None))

    def test_independent_candidate_scanner_matches_prefix_suffix_and_boundary_cases(self):
        snippets = ("USD 1,234.56", "-12.34 EUR", "CAD +20,00", "$12.34", "GBP\t12.34", "12,34 €",
                    "xUSD 12.34", "USD 12.34x", "USD 1.00EUR", "USD 2５０.00", "EUR 1\u202f234,56",
                    "1\u202f234,56 EUR", "(£ 12.34)", "USD 12.34GBP 13.00", "a_1.00USD", "USD 1.00$2.00")
        for snippet in snippets:
            with self.subTest(snippet=snippet):
                selected = request(snippet)
                self.assertEqual(audit.candidates(selected["state"]["text"]), selected["state"]["candidates"])

    def test_visible_currency_markers_declarations_and_unsupported_currency(self):
        for marker, declaration, expected in (("USD", "GBP", "USD"), ("EUR", "USD", "EUR"), ("GBP", "EUR", "GBP"),
                                              ("€", "USD", "EUR"), ("£", "USD", "GBP"), ("$", "EUR", "EUR"),
                                              ("¤", "GBP", "GBP"), ("$", "not stated", "review"), ("CAD", "USD", "review")):
            attributes = actual_attributes(request(marker + " 12.34", declaration=declaration))
            reference = audit.attributes(attributes["state"])
            self.assertEqual(reference["currency"], expected)
            self.assertTrue(reference["direction_known"])
            actual = normalize_amount(attributes, currency=expected, direction_known=True, is_credit=False)
            self.assertEqual(actual, audit.normalized(attributes["state"], expected, True, False))

    def test_unsigned_signed_conflicting_and_unknown_directions(self):
        for value, flow, known, credit in (("USD 12.34", "credit", True, True), ("USD -12.34", "credit", True, True),
                                          ("USD +12.34", "charge", True, False), ("USD -12.34", "charge", False, None),
                                          ("USD +12.34", "credit", False, None), ("USD -12.34", "not stated", False, None)):
            attributes = actual_attributes(request(value, flow))
            ref = audit.attributes(attributes["state"])
            self.assertEqual((ref["direction_known"], ref["is_credit"]), (known, credit))
            normal = normalize_amount(attributes, currency="USD", direction_known=known, is_credit=credit)
            self.assertEqual(normal, audit.normalized(attributes["state"], "USD", known, credit))
            if not known:
                forged = normalize_amount(attributes, currency="USD", direction_known=True, is_credit=True)
                self.assertEqual(forged["reason"], "direction_requires_review")

    def test_partial_candidates_cannot_be_rescued_by_counterfeit_predictions(self):
        for value, locale in (("EUR 1\u202f234,56", "EU"), ("1\u202f234,56 EUR", "EU"), ("(USD 12.34)", "US")):
            selected = request(value, "credit", locale=locale)
            self.assertTrue(selected["state"]["candidates"])
            for candidate_id in selected["state"]["candidates"]:
                attributes = actual_attributes(selected, candidate_id)
                ref = audit.attributes(attributes["state"])
                self.assertEqual((ref["currency"], ref["direction_known"], ref["is_credit"]), ("review", False, None))
                forged = normalize_amount(attributes, currency="EUR" if locale == "EU" else "USD", direction_known=True, is_credit=True)
                self.assertEqual(forged["reason"], "partial_or_unbound_candidate")

    def test_exact_long_decimal_credit_and_zero_ignore_decimal_context(self):
        for value, expected in (("USD -123456789012345678901234567890.12", "-123456789012345678901234567890.12"),
                                ("USD -0.00", "0.00")):
            attributes = actual_attributes(request(value, "credit"))
            with localcontext() as context:
                context.prec = 3
                actual = normalize_amount(attributes, currency="USD", direction_known=True, is_credit=True)
                independent = audit.normalized(attributes["state"], "USD", True, True)
            self.assertEqual(actual["amount"], expected)
            self.assertEqual(actual, independent)
        ledger = actual_attributes(request("1.234,56 EUR", "rebate", locale="EU", layout="ledger", declaration="EUR"))
        self.assertEqual(normalize_amount(ledger, currency="EUR", direction_known=True, is_credit=True)["amount"], "-1234.56")

    def test_ascii_numeric_grammar_rejects_mixed_unicode_malformed_grouping_and_signs(self):
        for text, locale in (("USD 2５０.00", "US"), ("USD 2٥0.00", "US"), ("USD 01.00", "US"),
                             ("USD 1.2", "US"), ("USD 1e3", "US"), ("EUR 1.234\u202f567,89", "EU"),
                             ("(USD -12.34)", "US"), ("USD 1,23.45", "US"), ("EUR 12.34", "EU")):
            self.assertIsNone(audit.money(text, locale))
            selected = request(text, locale=locale)
            self.assertTrue(audit.selection(selected["state"])["target_present"])
            for candidate_id in selected["state"]["candidates"]:
                attributes = actual_attributes(selected, candidate_id)
                self.assertFalse(audit.attributes(attributes["state"])["valid_amount"])
                self.assertEqual(normalize_amount(attributes, currency="USD", direction_known=True, is_credit=False)["status"], "review")

    def test_locale_headers_are_required_unique_and_consistent(self):
        original = document()
        for text in (original.replace("Number format: US\n", ""), original + "\nNumber format: US",
                     original.replace("Number format: US", "Number format: EU"), original + "\nCurrency declaration: EUR"):
            with self.assertRaises(ValueError):
                amount_selection(text, "due", locale="US")
        with self.assertRaises(TypeError):
            amount_selection(original, "due")
        with self.assertRaises(ValueError):
            amount_selection(original, "due", locale=None)

    def test_candidate_limit_no_candidates_and_actual_candidate_binding(self):
        text = document("not recorded") + "\n" + "\n".join("Memo USD 1.00" for _ in range(254))
        self.assertEqual(len(amount_selection(text, "due", locale="US")["state"]["candidates"]), 254)
        with self.assertRaisesRegex(ValueError, "More than 254"):
            amount_selection(text + "\nMemo USD 1.00", "due", locale="US")
        empty = request("not recorded")
        self.assertEqual(empty["state"]["candidates"], {})
        self.assertEqual(len(compile_request(**empty)[0]["options"]), 1)
        self.assertIsNone(amount_attributes(empty, "none"))
        with self.assertRaises(ValueError):
            amount_attributes(empty, "span_0")
        changed = request()
        changed["state"]["candidates"]["span_0"]["start"] += 1
        with self.assertRaises(ValueError):
            amount_attributes(changed, "span_0")
        changed = actual_attributes(request())
        changed["state"]["selected"]["end"] -= 1
        with self.assertRaises(ValueError):
            normalize_amount(changed, currency="USD", direction_known=True, is_credit=False)


class AmountCorpusAuditTest(unittest.TestCase):
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
        return [json.loads(line) for line in (self.directory / name).read_text().splitlines()]

    def write(self, name, values):
        (self.directory / name).write_text("".join(json.dumps(value, ensure_ascii=False) + "\n" for value in values))

    def reseal(self, update_summary=False):
        path = self.directory / "manifest.json"
        manifest = json.loads(path.read_text())
        manifest["files_sha256"] = {name: audit.sha256(self.directory / name) for name in manifest["files_sha256"]}
        if update_summary:
            rows = [row for split in SPLITS for row in self.read(split + ".jsonl")]
            manifest["summary"] = audit.validate_records(rows)
            manifest["counts"] = {split: sum(row["split"] == split for row in rows) for split in SPLITS}
        path.write_text(json.dumps(manifest))

    def test_original_dataset_counts_recall_and_all_candidate_attributes(self):
        result = audit.verify(self.directory)
        self.assertEqual((result["families"], result["documents"], result["typed_records"]), (3, 48, 744))
        self.assertEqual(result["candidate_count"], 222)
        self.assertEqual(result["candidate_recall"]["fraction"], "30/36")
        self.assertEqual(result["omitted_supervision_counts"], {"undefined_direction": 15, "forced_single_candidate": 3})
        self.assertEqual(generate(3, 42, 1), generate(3, 42, 1))

    def test_joint_selection_reference_and_target_mutation_is_rejected(self):
        cases = self.read("cases.jsonl")
        case = next(case for case in cases if case["variant"] == "due_charge")
        case["selection_reference"]["span"] = "none"
        rows = self.read(case["split"] + ".jsonl")
        row = next(row for row in rows if row["id"] == case["id"] + ":selection:request:span")
        row["target"] = [0.] * (len(row["options"]) - 1) + [1.]
        self.write("cases.jsonl", cases)
        self.write(case["split"] + ".jsonl", rows)
        self.reseal()
        with self.assertRaisesRegex(ValueError, "selection reference differs"):
            audit.verify(self.directory)

    def test_visible_flow_mutation_and_wrong_normalization_are_independently_detected(self):
        original = self.read("cases.jsonl")
        cases = copy.deepcopy(original)
        case = next(case for case in cases if case["variant"] == "due_charge")
        text = case["selection_request"]["state"]["text"]
        # Equal-length replacement preserves every candidate/target offset.
        changed = text.replace("| Flow: charge", "| Flow: credit", 1)
        case["selection_request"]["state"]["text"] = changed
        for item in case["attributes"]:
            item["request"]["state"]["text"] = changed
        rows = self.read(case["split"] + ".jsonl")
        for row in rows:
            if row["metadata"]["case_id"] == case["id"]:
                row["state"]["text"] = changed
        self.write("cases.jsonl", cases)
        self.write(case["split"] + ".jsonl", rows)
        self.reseal()
        with self.assertRaisesRegex(ValueError, "attribute reference differs"):
            audit.verify(self.directory)
        shutil.rmtree(self.directory)
        shutil.copytree(self.original, self.directory)
        cases = self.read("cases.jsonl")
        cases[0]["attributes"][0]["normalized_reference"]["amount"] = "999999.99"
        self.write("cases.jsonl", cases)
        self.reseal()
        with self.assertRaisesRegex(ValueError, "normalization differs"):
            audit.verify(self.directory)

    def test_undefined_is_credit_cannot_gain_a_false_supervised_target(self):
        cases = self.read("cases.jsonl")
        case = next(case for case in cases if case["variant"] == "unknown_direction")
        item = next(item for item in case["attributes"] if item["reference"]["is_credit"] is None)
        compiled = next(row for row in compile_request(**item["request"]) if row["id"] == "is_credit")
        rows = self.read(case["split"] + ".jsonl")
        base_id = f"{case['id']}:attributes:{item['candidate_id']}:"
        forged = copy.deepcopy(next(row for row in rows if row["id"] == base_id + "direction_known"))
        forged.update(id=base_id + "is_credit", question=compiled["question"], target=[1., 0.])
        forged["metadata"]["question_id"] = "is_credit"
        rows.append(forged)
        self.write(case["split"] + ".jsonl", rows)
        self.reseal(update_summary=True)
        with self.assertRaisesRegex(ValueError, "orphan typed record or supervised undefined head"):
            audit.verify(self.directory)

    def test_case_family_split_and_all_candidate_coverage_are_checked(self):
        initial = self.read("cases.jsonl")
        cases = copy.deepcopy(initial)
        cases[0]["split"] = "test" if cases[0]["split"] != "test" else "train"
        self.write("cases.jsonl", cases)
        self.reseal()
        with self.assertRaisesRegex(ValueError, "family linkage differs"):
            audit.verify(self.directory)
        cases = copy.deepcopy(initial)
        cases[0]["attributes"].pop()
        self.write("cases.jsonl", cases)
        self.reseal()
        with self.assertRaisesRegex(ValueError, "all actual A candidates"):
            audit.verify(self.directory)

    def test_source_hash_binding_and_unsealed_bytes_fail(self):
        path = self.directory / "manifest.json"
        initial = path.read_text()
        manifest = json.loads(initial)
        manifest["configuration"]["source_files_sha256"]["case_amount_extraction.py"] = "0" * 64
        path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "generator/runtime source hashes differ"):
            audit.verify(self.directory)
        path.write_text(initial)
        with (self.directory / "families.jsonl").open("a") as stream:
            stream.write("\n")
        with self.assertRaisesRegex(ValueError, "manifest file hashes differ"):
            audit.verify(self.directory)

    def test_hidden_labels_and_metadata_do_not_enter_candidate_prompts(self):
        _, _, rows = generate(2, 42, 1)
        for row in rows:
            before = candidate_prompts(row)
            changed = copy.deepcopy(row)
            changed.update(id="HIDDEN", target=[.5, .5], metadata={"gold": "HIDDEN"}, split="HIDDEN")
            self.assertEqual(candidate_prompts(changed), before)
            self.assertNotIn("reference", row["state"])
            if row["metadata"]["stage"] == "attributes":
                self.assertNotIn("requested_role", row["state"])

    def test_generator_refuses_existing_dataset(self):
        before = audit.sha256(self.directory / "manifest.json")
        with self.assertRaisesRegex(ValueError, "existing corpora are never overwritten"):
            build_dataset(self.directory, 3, 42, 1)
        self.assertEqual(audit.sha256(self.directory / "manifest.json"), before)

    def test_output_rejects_dataset_paths_aliases_existing_files_and_symlinks(self):
        alias = Path(self.temp.name) / "data-alias"
        alias.symlink_to(self.directory, target_is_directory=True)
        existing = Path(self.temp.name) / "existing.json"
        existing.write_text("preserve")
        linked = Path(self.temp.name) / "linked.json"
        linked.symlink_to(existing)
        dangling = Path(self.temp.name) / "dangling.json"
        dangling.symlink_to(Path(self.temp.name) / "missing.json")
        before = {path.name: path.read_bytes() for path in self.directory.iterdir()}
        for output in (self.directory / "manifest.json", self.directory / "train.jsonl", alias / "nested/report.json", existing, linked, dangling):
            with self.subTest(output=output), patch.object(audit, "verify", side_effect=AssertionError("must reject before reads")):
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
            output.write_text("arrived concurrently")
            return result

        with patch.object(audit, "verify", side_effect=concurrent), self.assertRaises(FileExistsError):
            audit.main(["--data", str(self.directory), "--output", str(output)])
        self.assertEqual(output.read_text(), "arrived concurrently")


if __name__ == "__main__":
    unittest.main()
