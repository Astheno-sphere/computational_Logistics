import copy
import hashlib
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from jev.api import compile_request
from jev.case_phone_extraction import (
    LIBRARY_VERSION, build_dataset, document_fields, generate, inspect_candidate,
    normalize_phone, phone_attributes, phone_candidates, phone_library, phone_selection,
    selection_reference,
)
from jev.data import validate_records

PHONE_AVAILABLE = importlib.util.find_spec("phonenumbers") is not None
requires_phone = unittest.skipUnless(PHONE_AVAILABLE, "requires the optional .[phone] extra")


def document(value="+1 202-555-0123", region="US", *, extras=(), layout="card"):
    line = f"Mobile: {value}" if layout == "card" else f"On-call contact :: phone={value}"
    if region is not None:
        line += f" | Region: {region}" if layout == "card" else f"; region={region}"
    return "\n".join(["Fictional contact; café 联系卡; do not dial.", *extras, line])


def selection(value="+1 202-555-0123", region="US", **kwargs):
    return phone_selection(document(value, region, **kwargs), "mobile", layout=kwargs.get("layout", "card"))


def attributes(value="+1 202-555-0123", region="US", **kwargs):
    request = selection(value, region, **kwargs)
    return phone_attributes(request, next(iter(request["state"]["candidates"])))


class PhoneRuntimeTest(unittest.TestCase):
    @requires_phone
    def test_optional_library_version_is_exact(self):
        self.assertEqual(phone_library().__version__, LIBRARY_VERSION)
        with patch.object(phone_library(), "__version__", "999"):
            with self.assertRaisesRegex(RuntimeError, "phonenumbers=="):
                phone_library()

    def test_missing_optional_library_has_explicit_install_hint(self):
        with patch.dict(sys.modules, {"phonenumbers": None}):
            with self.assertRaisesRegex(RuntimeError, r"optional extra: pip install.*phone"):
                phone_library()

    def test_request_builders_do_not_require_library(self):
        with patch("jev.case_phone_extraction.phone_library", side_effect=AssertionError("unexpected library call")):
            a = selection()
            b = phone_attributes(a, "span_0")
            self.assertEqual(len(compile_request(**a)), 2)
            self.assertEqual(len(compile_request(**b)), 1)
            self.assertIsNone(phone_attributes(a, "none"))

    def test_query_blind_candidates_and_character_offsets(self):
        text = document(extras=("Billing: +1 416-555-0156 | Region: CA",))
        mobile, billing = (phone_selection(text, role) for role in ("mobile", "billing"))
        self.assertEqual(mobile["state"]["candidates"], billing["state"]["candidates"])
        self.assertNotEqual(selection_reference(mobile)["span"], selection_reference(billing)["span"])
        for span in phone_candidates(text).values():
            self.assertEqual(text[span["start"]:span["end"]], span["text"])
            self.assertNotEqual(len(text[:span["start"]].encode()), span["start"])

    def test_presence_absence_ambiguity_and_miss_are_separate(self):
        for value, expected, present in (("not recorded", "target_absent", False), ("", "target_absent", False),
                                        ("1-800-FLOWERS", "candidate_miss", True), ("+44\u202f7700\u202f900123", "candidate_miss", True)):
            ref = selection_reference(selection(value))
            self.assertEqual((ref["reason"], ref["target_present"], ref["span"]), (expected, present, "none"))
        absent = phone_selection("Support: +1 202-555-0123 | Region: US", "mobile")
        self.assertEqual(selection_reference(absent)["reason"], "target_absent")
        duplicate = selection(extras=("Mobile: +1 202-555-0123 | Region: US",))
        self.assertEqual(selection_reference(duplicate)["reason"], "ambiguous_target")

    @requires_phone
    def test_repeated_phone_uses_offsets_and_wrong_selection_is_not_repaired(self):
        a = selection(extras=("Billing: +1 416-555-0156 | Region: CA",))
        self.assertEqual(selection_reference(a)["span"], "span_1")
        b = phone_attributes(a, "span_0")
        self.assertNotIn("requested_role", b["state"])
        normal = normalize_phone(b, region="CA")
        self.assertEqual(normal["e164"], "+14165550156")
        self.assertEqual(normal["selected"], a["state"]["candidates"]["span_0"])
        repeated = selection(extras=("Billing: +1 202-555-0123 | Region: US",))
        self.assertEqual(selection_reference(repeated)["span"], "span_1")

    def test_candidates_cannot_be_invented_or_shifted(self):
        a = selection()
        with self.assertRaises(ValueError):
            phone_attributes(a, "gold_span")
        altered = copy.deepcopy(a)
        altered["state"]["candidates"]["span_0"]["start"] += 1
        with self.assertRaises(ValueError):
            phone_attributes(altered, "span_0")
        b = phone_attributes(a, "span_0")
        b["state"]["selected"]["end"] -= 1
        with self.assertRaises(ValueError):
            normalize_phone(b, region="US")

    def test_missing_country_never_defaults_even_with_international_code(self):
        with patch("jev.case_phone_extraction.phone_library", side_effect=AssertionError("must not infer missing region")):
            for region in (None, "", "not stated"):
                for raw in ("+1 202-555-0123", "+1 416-555-0123", "+44 7700 900123", "202-555-0123"):
                    b = attributes(raw, region)
                    ref = inspect_candidate(b)
                    self.assertEqual((ref["region"], ref["reason"], ref["possible"]), ("unknown", "region_missing", None))
                    self.assertIsNone(normalize_phone(b, region="US")["e164"])

    def test_ambiguous_and_unsupported_declarations_require_review(self):
        for declaration in ("US,CA", "GB,JE", "FR", "US | Region: CA", "us"):
            ref = inspect_candidate(attributes(region=declaration))
            self.assertEqual((ref["region"], ref["reason"]), ("review", "unsupported_or_ambiguous_region"))

    @requires_phone
    def test_shared_calling_codes_do_not_override_explicit_region_conflicts(self):
        for raw, region in (("+1 416-555-0123", "US"), ("+1 202-555-0123", "CA"),
                            ("+44 7700 900123", "US"), ("+1 202-555-0123", "GB")):
            ref = inspect_candidate(attributes(raw, region))
            self.assertEqual((ref["region"], ref["reason"]), ("review", "region_phone_conflict"))
        gb = inspect_candidate(attributes("+44 7700 900123", "GB"))
        self.assertEqual((gb["region"], gb["declared_region"], gb["metadata_region"]), ("GB", "GB", None))

    @requires_phone
    def test_exact_e164_for_national_and_international_reserved_styles(self):
        cases = (("+1 202-555-0123", "US", "+12025550123"), ("202.555.0123", "US", "+12025550123"),
                 ("+1 416-555-0156", "CA", "+14165550156"), ("416 555 0156", "CA", "+14165550156"),
                 ("+44 7700 900123", "GB", "+447700900123"), ("07700 900123", "GB", "+447700900123"))
        for raw, region, expected in cases:
            normal = normalize_phone(attributes(raw, region), region=region)
            self.assertEqual((normal["status"], normal["e164"], normal["routable"]), ("formatted", expected, "unverified"))
            self.assertTrue(normal["possible"])

    @requires_phone
    def test_possible_valid_and_routable_are_not_equated(self):
        gb = normalize_phone(attributes("07700 900123", "GB"), region="GB")
        self.assertEqual((gb["possible"], gb["valid"], gb["valid_for_region"], gb["routable"]), (True, False, False, "unverified"))
        us = normalize_phone(attributes(), region="US")
        self.assertEqual((us["valid"], us["routable"]), (True, "unverified"))
        short = normalize_phone(attributes("202-555-01", "US"), region="US")
        self.assertEqual((short["status"], short["possible"], short["e164"]), ("review", False, None))

    @requires_phone
    def test_locally_possible_numbers_without_area_code_have_no_e164(self):
        for raw, region in ((raw, region) for raw in ("555-0123", "5550123", "+1 555-0123") for region in ("US", "CA")):
            normal = normalize_phone(attributes(raw, region), region=region)
            self.assertEqual((normal["status"], normal["reason"], normal["e164"]),
                             ("review", "local_only_number_missing_area_code", None))
            self.assertTrue(normal["possible"])
            self.assertFalse(normal["valid"])

    def test_partial_extensions_and_parentheses_cannot_be_rescued(self):
        for raw in ("+1 202-555-0123 ext. 45", "(+1 202-555-0123)", "(202) 555-0123"):
            a = selection(raw)
            self.assertEqual(selection_reference(a)["reason"], "candidate_miss")
            self.assertTrue(a["state"]["candidates"])
            for candidate in a["state"]["candidates"]:
                normal = normalize_phone(phone_attributes(a, candidate), region="US")
                self.assertEqual((normal["status"], normal["reason"], normal["e164"]), ("review", "partial_or_unbound_candidate", None))

    def test_unicode_vanity_and_malformed_format_do_not_reach_library(self):
        with patch("jev.case_phone_extraction.phone_library", side_effect=AssertionError("unsupported input sent to permissive parser")):
            for raw in ("２０２５５５０１２３", "202-555-٠١٢٣", "1-800-FLOWERS", "+44\u202f7700\u202f900123", "+1--202-555-0123", "+1  202-555-0123"):
                a = selection(raw)
                for candidate in a["state"]["candidates"]:
                    self.assertEqual(inspect_candidate(phone_attributes(a, candidate))["region"], "review")

    @requires_phone
    def test_implicit_trunk_or_idd_digit_repair_is_rejected(self):
        for raw, region in (("+44 07700 900123", "GB"), ("1 202 555 0123", "US"), ("0044 7700 900123", "GB"), ("011 44 7700 900123", "US")):
            normal = normalize_phone(attributes(raw, region), region=region)
            self.assertEqual(normal["status"], "review")
            self.assertIsNone(normal["e164"])

    def test_outside_field_candidates_are_retained_but_reviewed(self):
        a = selection(extras=("Archived note: +1 416-555-0123",))
        self.assertEqual(len(a["state"]["candidates"]), 2)
        normal = normalize_phone(phone_attributes(a, "span_0"), region="CA")
        self.assertEqual(normal["reason"], "partial_or_unbound_candidate")

    def test_policy_tampering_and_unknown_role_are_rejected(self):
        with self.assertRaises(ValueError):
            phone_selection(document(), "emergency")
        a = selection()
        a["state"]["policy"]["supported_regions"].append("FR")
        with self.assertRaises(ValueError):
            phone_attributes(a, "span_0")
        with self.assertRaises(ValueError):
            normalize_phone(attributes(), region="FR")

    def test_candidate_limit_is_explicit_and_zero_candidates_are_valid_api(self):
        with self.assertRaises(ValueError):
            phone_selection("\n".join("Mobile: 202-555-0123 | Region: US" for _ in range(255)), "mobile")
        request = selection("not recorded")
        self.assertEqual(list(request["questions"]["span"]["criteria"]), ["none"])
        self.assertEqual(len(compile_request(**request)), 2)

    @requires_phone
    def test_message_layout_preserves_public_role_and_region_semantics(self):
        a = selection("07700 900123", "GB", layout="message")
        fields = document_fields(a["state"]["text"], a["state"]["policy"])
        self.assertEqual((fields[0]["role"], fields[0]["region"]), ("mobile", "GB"))
        self.assertEqual(normalize_phone(phone_attributes(a, "span_0"), region="GB")["e164"], "+447700900123")


@requires_phone
class PhoneDatasetTest(unittest.TestCase):
    def test_all_candidates_and_document_variants_keep_family_split(self):
        families, cases, rows = generate(groups=6, ood_groups=2)
        validate_records(rows)
        self.assertEqual((len(families), len(cases)), (6, 120))
        family_splits = {family["id"]: family["split"] for family in families}
        observed_orders = set()
        for case in cases:
            self.assertEqual(case["split"], family_splits[case["family_id"]])
            state = case["selection_request"]["state"]
            self.assertIn("Fictional", state["text"])
            self.assertEqual(set(state["candidates"]), {item["candidate_id"] for item in case["attributes"]})
            self.assertEqual(state["policy"]["layout"], "message" if case["split"] == "ood" else "card")
            self.assertNotIn(case["variant"], state["text"])
            observed_orders.add(tuple(field["role"] for field in document_fields(state["text"], state["policy"])))
        self.assertGreater(len(observed_orders), 6)
        self.assertEqual(sum(case["selection_reference"]["reason"] == "candidate_miss" for case in cases), 18)

    def test_manifest_binds_source_and_artifacts_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)/"data"
            manifest = build_dataset(output, groups=2, ood_groups=1)
            self.assertEqual((manifest["family_count"], manifest["document_count"]), (2, 40))
            self.assertEqual(manifest["omitted_supervision_counts"], {"forced_single_candidate": 2})
            for name, digest in manifest["files_sha256"].items():
                self.assertEqual(hashlib.sha256((output/name).read_bytes()).hexdigest(), digest)
            self.assertFalse(manifest["training_performed"])
            self.assertFalse(manifest["model_inference_performed"])
            with self.assertRaises(ValueError):
                build_dataset(output, groups=2, ood_groups=1)
            link = Path(temporary)/"linked"
            link.symlink_to(output, target_is_directory=True)
            with self.assertRaises(ValueError):
                build_dataset(link, groups=2, ood_groups=1)


if __name__ == "__main__":
    unittest.main()
