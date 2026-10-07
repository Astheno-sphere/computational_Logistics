from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

import pandas as pd

from mapmover.runtime import external_reference_adapters as adapters
from mapmover.runtime import reference_exchange


EQUIVALENCE = adapters.ExternalReferenceEdge(
    external_id="11111111-1111-1111-1111-111111111111", loc_id="CAN-AB-4803-003",
    relationship_type="equivalent_identity", is_primary=True, source_release="gers-2026-07",
    internal_release="can-spine-v1", country="CAN", source_level=3, external_subtype="county",
    identity_confidence="high", geometry_confidence=0.94, external_name="Division 3",
    loc_name="Division No. 3", edge_id="edge-equivalent", partition_id="partition-can",
    bridge_generation_id="generation-2", edge_content_hash="sha256:unchanged-edge",
)
PART_OF = replace(
    EQUIVALENCE, external_id="22222222-2222-2222-2222-222222222222", loc_id="CAN-AB",
    relationship_type="contained_by", external_subtype="region", edge_id="edge-contained",
    edge_content_hash="sha256:changed-edge",
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _frame(external_id: str, loc_id: str, country: str, internal: str) -> pd.DataFrame:
    return pd.DataFrame([{
        "gers_division_id": external_id, "loc_id": loc_id, "relationship_type": "equivalence",
        "is_primary": True, "overture_release": "gers-2026-07", "spine_vintage": internal,
        "iso3": country, "admin_level": 2, "overture_subtype": "county",
        "identity_confidence": "high", "geometry_confidence": 0.9,
        "edge_id": f"edge-{country.lower()}", "bridge_generation_id": "generation-1",
        "edge_content_hash": f"sha256:{country.lower()}",
    }])


def _write_contract(root: Path, specs: list[tuple[str, str, str, str]], *, admitted: bool = True) -> dict:
    adapter = adapters.get_external_adapter("gers")
    partitions = []
    for number, (country, internal, external_id, loc_id) in enumerate(specs):
        forward = root / f"{country}-{number}-forward.parquet"
        reverse = root / f"{country}-{number}-reverse.parquet"
        frame = _frame(external_id, loc_id, country, internal)
        frame.to_parquet(forward, index=False)
        frame.to_parquet(reverse, index=False)
        partitions.append({
            "country_iso3": country, "internal_spine_release": internal,
            "partition_fingerprint": hashlib.sha256(f"{country}:{internal}:{number}".encode()).hexdigest(),
            "artifacts": {
                "by_external_id": {"path": forward.name, "sha256": _sha(forward)},
                "by_internal_id": {"path": reverse.name, "sha256": _sha(reverse)},
            },
        })
    identity = {"external_system": "overture_gers", "external_release": "gers-2026-07", "adapter": {}, "partitions": partitions}
    state = "published" if admitted else "candidate_blocked"
    manifest = {
        "profile": "external_reference_bridge", **identity,
        "release_fingerprint": adapters.stable_fingerprint(identity),
        "status": "admitted" if admitted else state, "publication_state": state,
        "publication": {"state": state, "hosted_publication_cleared": admitted},
        "source_license": {"license": "fixture-license", "license_review_status": "approved"},
    }
    release = root / "release.json"
    release.write_text(json.dumps(manifest), encoding="utf-8")
    pointer = root / adapter.pointer_path
    pointer.parent.mkdir(parents=True, exist_ok=True)
    pointer.write_text(json.dumps({
        "profile": "external_reference_bridge_pointer", "release_manifest": release.name,
        "release_fingerprint": manifest["release_fingerprint"],
    }), encoding="utf-8")
    return manifest


class ExternalReferenceRegistryTests(unittest.TestCase):
    def test_second_provider_adapter_is_loaded_from_the_admitted_catalog(self) -> None:
        record = {
            "external_system": "example_ids",
            "adapter": {
                "label": "Example IDs", "aliases": ["example"],
                "identifier_pattern": r"EX-[0-9]+",
                "columns": {
                    "external_id_column": "external_id", "internal_id_column": "loc_id",
                    "source_release_column": "source_release",
                    "internal_release_column": "internal_release",
                    "country_column": "iso3",
                },
            },
        }
        with mock.patch(
            "mapmover.runtime.geometry_catalog.load_geometry_catalog",
            return_value={"external_reference_bridges": [record]},
        ):
            adapter = adapters.get_external_adapter("example")
        self.assertIsNotNone(adapter)
        self.assertEqual("example_ids", adapter.system)
        self.assertTrue(adapters.identifier_matches(adapter, "EX-123"))

    def test_no_current_registry_and_candidate_registry_both_fail_closed(self) -> None:
        adapter = adapters.get_external_adapter("gers")
        with tempfile.TemporaryDirectory() as temporary, mock.patch.object(adapters, "DATA_ROOT", Path(temporary)):
            self.assertFalse(adapters.adapter_available(adapter))
            _write_contract(Path(temporary), [("USA", "usa-v1", EQUIVALENCE.external_id, "USA-VA-059")], admitted=False)
            self.assertFalse(adapters.adapter_available(adapter))
            self.assertEqual(adapters.lookup_external_edges("gers", EQUIVALENCE.external_id), [])

    def test_configured_but_unadmitted_system_reports_unavailable(self) -> None:
        with mock.patch.object(reference_exchange, "adapter_available", return_value=False):
            payload = reference_exchange.resolve_external_reference("gers", EQUIVALENCE.external_id)
        self.assertEqual(payload["error"]["code"], "external_system_unavailable")

    def test_local_pointer_cannot_escape_the_data_root(self) -> None:
        adapter = adapters.get_external_adapter("gers")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pointer = root / adapter.pointer_path
            pointer.parent.mkdir(parents=True, exist_ok=True)
            pointer.write_text(json.dumps({
                "profile": "external_reference_bridge_pointer",
                "release_manifest": "../outside.json",
                "release_fingerprint": "a" * 64,
            }), encoding="utf-8")
            with mock.patch.object(adapters, "DATA_ROOT", root):
                self.assertIsNone(adapters.admitted_bridge(adapter))

    def test_unscoped_batch_lookup_fans_out_once_across_all_admitted_partitions(self) -> None:
        specs = [
            ("USA", "usa-v2", "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "USA-VA-059"),
            ("CAN", "can-v1", "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", "CAN-AB-4803-003"),
        ]
        expected = {external: [loc_id] for _, _, external, loc_id in specs}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_contract(root, specs)
            with mock.patch.object(adapters, "DATA_ROOT", root), mock.patch.object(adapters, "run_df", wraps=adapters.run_df) as query:
                actual = adapters.external_primary_loc_ids("gers", list(expected))
            self.assertEqual(actual, expected)
            self.assertEqual(query.call_count, 1)

    def test_reverse_lookup_uses_the_reverse_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_contract(root, [("CAN", "can-v1", EQUIVALENCE.external_id, EQUIVALENCE.loc_id)])
            with mock.patch.object(adapters, "DATA_ROOT", root):
                edges = adapters.lookup_loc_id_edges("gers", EQUIVALENCE.loc_id)
            self.assertEqual([edge.external_id for edge in edges], [EQUIVALENCE.external_id])
            self.assertEqual(edges[0].edge_content_hash, "sha256:can")

    def test_bidirectional_admission_refuses_a_corrupt_reverse_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = _write_contract(root, [("CAN", "can-v1", EQUIVALENCE.external_id, EQUIVALENCE.loc_id)])
            reverse = root / manifest["partitions"][0]["artifacts"]["by_internal_id"]["path"]
            reverse.write_bytes(b"corrupt")
            with mock.patch.object(adapters, "DATA_ROOT", root):
                self.assertFalse(adapters.adapter_available(adapters.get_external_adapter("gers")))
                self.assertEqual(adapters.lookup_external_edges("gers", EQUIVALENCE.external_id), [])

    def test_hosted_catalog_is_the_normalized_descriptor(self) -> None:
        partition = {
            "country_iso3": "CAN", "internal_spine_release": "can-v1", "partition_fingerprint": "a" * 64,
            "artifacts": {
                "by_external_id": {"path": "cloud/by-external.parquet", "sha256": "b" * 64},
                "by_internal_id": {"path": "cloud/by-internal.parquet", "sha256": "c" * 64},
            },
        }
        identity = {"external_system": "overture_gers", "external_release": "gers-2026-07", "adapter": {}, "partitions": [partition]}
        record = {
            **identity, "release_fingerprint": adapters.stable_fingerprint(identity), "status": "admitted",
            "publication_state": "published", "publication": {"state": "published", "hosted_publication_cleared": True},
            "source_license": {"license": "catalog-owned"},
        }
        with mock.patch.object(adapters, "is_cloud_mode", return_value=True), mock.patch(
            "mapmover.runtime.geometry_catalog.load_geometry_catalog", return_value={"external_reference_bridges": [record]},
        ):
            bridge = adapters.admitted_bridge(adapters.get_external_adapter("gers"))
            discovery = adapters.adapter_public_entry(adapters.get_external_adapter("gers"))
        self.assertEqual(bridge.partitions[0].forward_path, "cloud/by-external.parquet")
        self.assertEqual(bridge.partitions[0].reverse_path, "cloud/by-internal.parquet")
        self.assertEqual(discovery["license"], {"license": "catalog-owned"})
        self.assertNotIn("partitions", discovery)

    def test_hosted_compact_catalog_does_not_require_partition_inventory(self) -> None:
        record = {
            "external_system": "overture_gers",
            "external_release": "gers-2026-07",
            "adapter": {},
            "release_fingerprint": "d" * 64,
            "status": "admitted",
            "publication_state": "published",
            "publication": {"state": "published", "hosted_publication_cleared": True},
            "runtime_layout": "compact_parquet",
            "runtime_artifact": {
                "path": "cloud/overture-bridge.parquet",
                "sha256": "e" * 64,
            },
            "source_license": {"license": "catalog-owned"},
        }
        with mock.patch.object(adapters, "is_cloud_mode", return_value=True), mock.patch(
            "mapmover.runtime.geometry_catalog.load_geometry_catalog",
            return_value={"external_reference_bridges": [record]},
        ):
            bridge = adapters.admitted_bridge(adapters.get_external_adapter("gers"))

        self.assertIsNotNone(bridge)
        self.assertEqual(bridge.partitions, ())
        self.assertEqual(bridge.runtime_path, "cloud/overture-bridge.parquet")


class ExternalReferenceRuntimeTests(unittest.TestCase):
    def test_relationship_only_edge_never_resolves_as_identity(self) -> None:
        with mock.patch.object(reference_exchange, "adapter_available", return_value=True), mock.patch.object(reference_exchange, "lookup_external_edges", return_value=[PART_OF]):
            payload = reference_exchange.resolve_external_reference("gers", PART_OF.external_id)
        self.assertEqual(payload["status"], "relationship_only")
        self.assertIsNone(payload["resolved_loc_id"])

    def test_equivalence_reports_stable_provenance_without_row_history(self) -> None:
        with mock.patch.object(reference_exchange, "adapter_available", return_value=True), mock.patch.object(reference_exchange, "lookup_external_edges", return_value=[EQUIVALENCE]):
            payload = reference_exchange.resolve_external_reference("gers", EQUIVALENCE.external_id)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["edge_id"], "edge-equivalent")
        self.assertEqual(payload["edge_content_hash"], "sha256:unchanged-edge")
        self.assertNotIn("first_observed_at", payload)
        self.assertNotIn("scope_id", payload)

    def test_conflicting_equivalence_fails_closed_instead_of_ranking(self) -> None:
        conflicting = replace(EQUIVALENCE, loc_id="CAN-AB-OTHER", identity_confidence="low", geometry_confidence=1.0)
        with mock.patch.object(reference_exchange, "adapter_available", return_value=True), mock.patch.object(reference_exchange, "lookup_external_edges", return_value=[conflicting, EQUIVALENCE]):
            payload = reference_exchange.resolve_external_reference("gers", EQUIVALENCE.external_id)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status"], "conflicting_equivalence")
        self.assertIsNone(payload["resolved_loc_id"])

    def test_reverse_results_keep_stable_provenance_only(self) -> None:
        with mock.patch.object(reference_exchange, "admitted_external_adapters", return_value=[adapters.get_external_adapter("gers")]), mock.patch.object(
            reference_exchange, "lookup_loc_id_edges", return_value=[EQUIVALENCE, PART_OF]
        ), mock.patch.object(reference_exchange, "_crosswalk_artifacts", return_value=[]):
            payload = reference_exchange.loc_id_references(EQUIVALENCE.loc_id, systems=["gers"])
        external = [row for row in payload["references"] if row["system"] == "overture_gers"]
        self.assertEqual([row["edge_content_hash"] for row in external], ["sha256:unchanged-edge", "sha256:changed-edge"])
        self.assertTrue(all("scope_id" not in row and "last_verified_at" not in row for row in external))

    def test_convert_loc_id_to_external_bridge_skips_general_crosswalks(self) -> None:
        with mock.patch.object(
            reference_exchange, "lookup_loc_id_edges", return_value=[EQUIVALENCE]
        ) as lookup, mock.patch.object(
            reference_exchange, "_direct_crosswalk_matches"
        ) as general_crosswalk:
            payload = reference_exchange.convert_reference(
                from_system="loc_id",
                value=EQUIVALENCE.loc_id,
                to_system="gers",
                iso3="USA",
            )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["loc_id"], EQUIVALENCE.loc_id)
        self.assertEqual(payload["results"][0]["value"], EQUIVALENCE.external_id)
        general_crosswalk.assert_not_called()
        lookup.assert_called_once_with(
            "overture_gers",
            EQUIVALENCE.loc_id,
            country_scope="CAN",
            source_release=None,
            internal_release=None,
            limit=10,
        )


if __name__ == "__main__":
    unittest.main()
