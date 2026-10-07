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

from jev.api import candidate_prompts
from jev.case_citation import build_dataset, generate, locate_quote
from jev.data import SPLITS


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("citation_control_audit", ROOT / "reports/citation-control-v1/verify.py")
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def source(ood=False, *, amount="USD 100", day="2028-02-29", visitor="no"):
    """Handwritten source fixture, independent of the corpus renderer/specification."""
    entries = [("R-000000000001", amount, day, visitor)] + [
        (f"R-{index:012x}", "USD 100", "2028-02-29", "no") for index in range(2, 7)]
    if ood:
        lines = ["Operations note: Handwritten example", "A. Boundaries",
                 "The earliest qualifying request date is 2028-02-29, inclusive. The amount ceiling is USD 100, inclusive.",
                 'The decision "qualifies" is assigned if and only if both boundaries hold, except for the exclusion in B.',
                 "B. Exclusion",
                 "A visitor value of yes rules out qualification; no leaves the boundary rules in effect. Only these rules determine eligibility. Missing entries remain unknown.",
                 "C. Register"]
        lines.extend(f"{rid} | requested amount: {value} | dated: {when} | visitor: {status}"
                     for rid, value, when, status in entries)
        lines.extend(["D. Costs", "The voucher covers no delivery charges.", "E. Unrelated notice"])
    else:
        lines = ["Policy: Handwritten example", "Section 1 — Eligibility",
                 'Subject to Section 2, the label "qualifies" applies exactly when the amount is no more than USD 100 and the request date is on or after 2028-02-29.',
                 "Section 2 — Exception",
                 "Visitor status yes disqualifies a request even when both conditions in Section 1 hold. Visitor status no does not trigger this exception. These are the complete eligibility rules; an unrecorded field stays unknown.",
                 "Section 3 — Register"]
        lines.extend(f"Request {rid}: amount {value}; request date {when}; visitor status {status}."
                     for rid, value, when, status in entries)
        lines.extend(["Section 4 — Charges", "Delivery charges are not covered by this voucher.", "Section 5 — Unrelated notice"])
    lines.append("A printing notice dated 2030-01-01 lists a budget of USD 300. This budget concerns posters, not vouchers.")
    return "\n".join(lines)


POSITIVE = "Request R-000000000001 qualifies for the voucher."
NEGATIVE = "Request R-000000000001 does not qualify for the voucher."


class CitationSemanticsTest(unittest.TestCase):
    def test_inclusive_amount_and_leap_date_boundaries_in_both_grammars(self):
        for ood in (False, True):
            self.assertEqual(audit.semantic_label(source(ood), POSITIVE), "supported")
            self.assertEqual(audit.semantic_label(source(ood), NEGATIVE), "contradicted")
            for changed in ({"amount": "USD 101"}, {"day": "2028-02-28"}, {"visitor": "yes"}):
                with self.subTest(ood=ood, changed=changed):
                    text = source(ood, **changed)
                    self.assertEqual(audit.semantic_label(text, POSITIVE), "contradicted")
                    self.assertEqual(audit.semantic_label(text, NEGATIVE), "supported")

    def test_unknown_completions_and_dominating_known_failure(self):
        for ood in (False, True):
            for field in ("amount", "day", "visitor"):
                with self.subTest(ood=ood, field=field):
                    text = source(ood, **{field: "not recorded"})
                    self.assertEqual(audit.semantic_label(text, POSITIVE), "insufficient")
                    self.assertEqual(audit.semantic_label(text, NEGATIVE), "insufficient")
            for changed in ({"amount": "not recorded", "visitor": "yes"},
                            {"day": "not recorded", "amount": "USD 101"},
                            {"visitor": "not recorded", "day": "2028-02-28"}):
                text = source(ood, **changed)
                self.assertEqual(audit.semantic_label(text, POSITIVE), "contradicted")
                self.assertEqual(audit.semantic_label(text, NEGATIVE), "supported")
            text = source(ood, amount="not recorded", day="not recorded", visitor="not recorded")
            self.assertEqual(audit.semantic_label(text, POSITIVE), "insufficient")

    def test_delivery_negation_and_irrelevant_numbers(self):
        for ood in (False, True):
            text = source(ood).replace("USD 300", "USD 1").replace("2030-01-01", "2000-01-01")
            self.assertEqual(audit.semantic_label(text, POSITIVE), "supported")
            self.assertEqual(audit.semantic_label(text, "The voucher covers delivery charges."), "contradicted")
            self.assertEqual(audit.semantic_label(text, "The voucher does not cover delivery charges."), "supported")

    def test_unsupported_rules_ambiguous_registers_and_claims_fail_closed(self):
        for text in (source().replace("no more than", "more than"),
                     source() + "\nAll exceptions are cancelled.",
                     source().replace("R-000000000002", "R-000000000001"),
                     source(day="2028-02-30")):
            with self.assertRaises(ValueError):
                audit.semantic_label(text, POSITIVE)
        for claim in (POSITIVE.replace("000000000001", "000000000999"), "The request probably qualifies."):
            with self.assertRaises(ValueError):
                audit.semantic_label(source(), claim)

    def test_quote_gate_only_normalizes_typography_and_whitespace(self):
        text = 'The label "qualifies" applies here.'
        quote = 'The  label\n“qualifies”   applies here.'
        self.assertEqual(audit.quote_status(text, None), "not_requested")
        self.assertEqual(audit.quote_status(text, text), "exact")
        self.assertEqual(audit.quote_status(text, quote), "normalized")
        self.assertEqual(locate_quote(text, quote), {"status": "located", "normalized_start": 0, "normalized_end": len(text)})
        for altered in (text.upper(), text.replace("applies", "works"), text.replace("The", "Ｔｈｅ"), text + " Always."):
            self.assertEqual(audit.quote_status(text, altered), "quote_not_found")
            self.assertEqual(locate_quote(text, altered), {"status": "quote_not_found"})
        for quote in ("", " \n "):
            with self.assertRaises(ValueError):
                locate_quote(text, quote)


class CitationCorpusAuditTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = tempfile.TemporaryDirectory()
        cls.original = Path(cls.base.name) / "original"
        build_dataset(cls.original, groups=12, seed=42, ood_groups=3)

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

    def test_original_corpus_audits_and_generation_is_deterministic(self):
        result = audit.verify(self.directory)
        self.assertTrue(result["verified"])
        self.assertEqual((result["documents"], result["cases"], result["semantic_records"]), (12, 264, 240))
        self.assertEqual(result["label_counts"], {"supported": 84, "contradicted": 84, "insufficient": 72})
        self.assertEqual(result["gate_counts"]["quote_not_found"], 24)
        self.assertEqual(generate(12, 42, 3), generate(12, 42, 3))

    def test_auxiliary_spec_is_not_the_semantic_oracle(self):
        documents = self.read("documents.jsonl")
        for doc in documents:
            doc["spec"] = {"untrusted": "All requests qualify; intentionally wrong auxiliary fixture."}
        self.write("documents.jsonl", documents)
        self.reseal()
        self.assertTrue(audit.verify(self.directory)["verified"])

    def test_matching_wrong_reference_and_target_are_rejected(self):
        cases = self.read("cases.jsonl")
        case = next(case for case in cases if case.get("reference_relation") == "supported")
        case["reference_relation"] = "contradicted"
        rows = self.read(case["split"] + ".jsonl")
        row = next(row for row in rows if row["id"] == case["semantic_record_id"])
        row["target"] = [0., 1., 0.]
        self.write(case["split"] + ".jsonl", rows)
        self.write("cases.jsonl", cases)
        self.reseal()
        with self.assertRaisesRegex(ValueError, "reference relation differs from rendered text"):
            audit.verify(self.directory)

    def test_final_rendered_fact_change_is_detected_despite_unchanged_auxiliary_spec(self):
        docs = self.read("documents.jsonl")
        doc = docs[0]
        before = doc["text"]
        parsed = audit.parse_source(before)
        rid = next(rid for rid, fact in parsed["requests"].items()
                   if fact["amount"] == parsed["cap"] and fact["date"] == parsed["start"])
        lines = before.splitlines()
        lines = [line.replace("visitor status no.", "visitor status yes.") if rid in line else line for line in lines]
        doc["text"] = after = "\n".join(lines)
        self.assertNotEqual(before, after)
        cases = self.read("cases.jsonl")
        for case in cases:
            if case["doc_id"] == doc["id"]:
                state = case["input"] if case["request"] is None else case["request"]["state"]
                state["source"] = after
        rows = self.read(doc["split"] + ".jsonl")
        for row in rows:
            if row["group_id"] == doc["group_id"]:
                row["state"]["source"] = after
        self.write("documents.jsonl", docs)
        self.write("cases.jsonl", cases)
        self.write(doc["split"] + ".jsonl", rows)
        self.reseal()
        with self.assertRaisesRegex(ValueError, "reference relation differs from rendered text"):
            audit.verify(self.directory)

    def test_absent_quote_cannot_acquire_confidence_or_a_semantic_record(self):
        initial = self.read("cases.jsonl")
        for field, value in (("confidence", .9), ("probabilities", {"supported": 1.}),
                             ("reference_relation", "supported"), ("semantic_record_id", "ghost")):
            with self.subTest(field=field):
                cases = copy.deepcopy(initial)
                case = next(case for case in cases if case["request"] is None)
                case[field] = value
                self.write("cases.jsonl", cases)
                self.reseal()
                with self.assertRaisesRegex(ValueError, "case fields differ|absent quote has a semantic record"):
                    audit.verify(self.directory)

    def test_gate_offsets_and_typography_modes_are_checked(self):
        cases = self.read("cases.jsonl")
        case = next(case for case in cases if case["gate"]["status"] == "located")
        case["gate"]["normalized_start"] += 1
        self.write("cases.jsonl", cases)
        self.reseal()
        with self.assertRaisesRegex(ValueError, "quote gate differs"):
            audit.verify(self.directory)

    def test_entire_source_document_and_claims_remain_in_one_split(self):
        cases = self.read("cases.jsonl")
        case = cases[0]
        case["split"] = "test" if case["split"] != "test" else "train"
        self.write("cases.jsonl", cases)
        self.reseal()
        with self.assertRaisesRegex(ValueError, "document linkage differs"):
            audit.verify(self.directory)

    def test_unsealed_bytes_fail_before_semantic_audit(self):
        with (self.directory / "documents.jsonl").open("a") as stream:
            stream.write("\n")
        with self.assertRaisesRegex(ValueError, "manifest file hashes differ"):
            audit.verify(self.directory)

    def test_labels_ids_provenance_and_specs_are_absent_from_model_inputs(self):
        _, _, rows = generate(2)
        for row in rows:
            self.assertEqual(set(row["state"]), {"claim", "source", "quote"})
            before = candidate_prompts(row)
            changed = copy.deepcopy(row)
            changed.update(id="HIDDEN", group_id="HIDDEN", split="HIDDEN", target=[.2, .3, .5],
                           metadata={"reference_relation": "HIDDEN", "spec": "HIDDEN"})
            self.assertEqual(candidate_prompts(changed), before)

    def test_build_refuses_to_overwrite_existing_corpus(self):
        before = audit.sha256(self.directory / "manifest.json")
        with self.assertRaisesRegex(ValueError, "existing corpora are never overwritten"):
            build_dataset(self.directory, groups=12)
        self.assertEqual(audit.sha256(self.directory / "manifest.json"), before)

    def test_report_cannot_write_inside_input_data_or_through_directory_alias(self):
        alias = Path(self.temp.name) / "data-alias"
        alias.symlink_to(self.directory, target_is_directory=True)
        before = {path.name: path.read_bytes() for path in self.directory.iterdir()}
        for output in (self.directory / "manifest.json", self.directory / "train.jsonl",
                       self.directory / "new-report.json", self.directory / "nested/report.json",
                       alias / "new-report.json"):
            with self.subTest(output=output), patch.object(audit, "verify", side_effect=AssertionError("must reject before reading")):
                with self.assertRaisesRegex(ValueError, "outside the input data directory"):
                    audit.main(["--data", str(self.directory), "--output", str(output)])
        self.assertEqual({path.name: path.read_bytes() for path in self.directory.iterdir()}, before)

    def test_report_refuses_existing_files_and_normal_or_dangling_symlinks(self):
        existing = Path(self.temp.name) / "existing-audit.json"
        existing.write_text("preserve this previous report")
        alias = Path(self.temp.name) / "report-alias.json"
        alias.symlink_to(existing)
        dangling = Path(self.temp.name) / "dangling-report.json"
        dangling.symlink_to(Path(self.temp.name) / "missing-report.json")
        for output in (existing, alias, dangling):
            with self.subTest(output=output), patch.object(audit, "verify", side_effect=AssertionError("must reject before reading")):
                with self.assertRaisesRegex(ValueError, "already exists|must not be a symlink"):
                    audit.main(["--data", str(self.directory), "--output", str(output)])
        self.assertEqual(existing.read_text(), "preserve this previous report")
        self.assertTrue(dangling.is_symlink())

    def test_report_can_only_create_a_new_file_and_uses_exclusive_open(self):
        output = Path(self.temp.name) / "new-audit.json"
        with redirect_stdout(io.StringIO()):
            self.assertEqual(audit.main(["--data", str(self.directory), "--output", str(output)]), 0)
        self.assertTrue(json.loads(output.read_text())["verified"])
        output.unlink()
        original_verify = audit.verify

        def another_writer_arrives(directory):
            result = original_verify(directory)
            output.write_text("concurrent report must survive")
            return result

        with patch.object(audit, "verify", side_effect=another_writer_arrives):
            with self.assertRaises(FileExistsError):
                audit.main(["--data", str(self.directory), "--output", str(output)])
        self.assertEqual(output.read_text(), "concurrent report must survive")


if __name__ == "__main__":
    unittest.main()
