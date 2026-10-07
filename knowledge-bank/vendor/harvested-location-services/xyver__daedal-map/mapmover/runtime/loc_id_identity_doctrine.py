from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from typing import Any

from .geography_reference import classify_loc_id_family

IDENTITY_ROLES = {
    "loc_id",
    "entity_id",
    "event_id",
    "route_id",
    "segment_id",
    "reach_id",
    "grid_id",
    "relationship_id",
    "crosswalk_id",
    "membership_set_id",
    "source_alias",
}

PUBLIC_PROMISES = {
    "stable_public",
    "public_alias",
    "internal",
    "private",
    "source_id",
    "blocked",
    "undecided",
}

ADMIN_FAMILIES = {
    "admin_0",
    "admin_local",
    "admin_geometry",
    "regional_base",
    "country_admin_extension",
}

SIDECHAIN_FAMILIES = {
    "overlay_zcta",
    "overlay_tribal",
    "overlay_nws_public_zone",
    "overlay_nws_fire_weather_zone",
    "postal",
    "water_body",
    "marine_eez",
    "marine_jurisdiction",
    "watershed",
    "protected_area",
    "ecoregion",
    "forest",
    "urban_area",
    "municipality",
    "electoral",
    "school_district",
    "health_region",
    "service_territory",
    "hazard_zone",
    "named_feature",
    "custom_private",
}

REFERENCE_LEVELS = {"label_0", "label_1", "label_2", "label_3", "label_4", "label_5"}

REFERENCE_LEVEL_REASONS = {
    "admin_spine",
    "official_admin_equivalent",
    "scale_hint",
    "source_native_hierarchy",
    "temporal_spine_version",
    "unresolved",
}

CONTAINMENT_METHODS = {
    "full_geometry",
    "centroid",
    "largest_overlap",
    "declared_by_source",
    "none",
}

SOURCE_FAMILY_PREFIXES = {
    "EEZ",
    "HYBAS",
    "HUC",
    "IHO1953",
    "MRGID",
    "WDPA",
    "WWF",
    "WWF-ECO",
    "OSM",
}

COUNTRY_SCOPED_SIDECHAIN_PATTERNS = (
    re.compile(r"^[A-Z]{3}-Z-\d{5}$"),
    re.compile(r"^[A-Z]{3}-FSA-[A-Z]\d[A-Z]$"),
    re.compile(r"^[A-Z]{3}-POA-\d{4}$"),
    re.compile(r"^[A-Z]{3}-TRIBAL-[A-Z0-9]+$"),
    re.compile(r"^[A-Z]{3}-NWS[ZF]Z-[A-Z]{2}Z\d{3}$"),
    re.compile(
        r"^[A-Z]{3}(?:-[A-Z0-9]+)*-(?:POSTAL|INDIGENOUS|WEATHER|FIREWX|PLACE|URBAN|"
        r"ELECTORAL|SCHOOL|HEALTH|WATERSHED|PROTECTED|WATER|ECOLOGICAL|TIMEZONE|PROGRAM)-"
        r"[A-Z0-9][A-Z0-9-]*$"
    ),
)

EVENT_MARKERS = {"EQ", "FIRE", "FLOOD", "HRCN", "TORN", "TSUN", "VOLC", "ALERT"}
GRID_PREFIXES = {"H3", "S2", "OLC", "PLUSCODE", "ERA5", "CMIP", "OISST", "SENTINEL"}
ROUTE_PREFIXES = {"ROUTE", "ROAD", "TRAIL", "RIVER"}
SEGMENT_PREFIXES = {"SEGMENT", "REACH", "WAY", "LINE"}

SPATIALLY_PLACEABLE_ROLES = {"loc_id", "entity_id", "route_id", "segment_id"}

ORACLE_FIELDS = {
    "role": "expected_role",
    "first_segment_scope": "expected_first_segment_scope",
    "parent_semantics": "expected_parent_semantics",
    "reference_level": "expected_reference_level",
    "placement_semantics": "expected_placement_semantics",
}

DESIGNATION_ORACLE_FIELDS = {
    "represents_membership_set": "membership_set_representation",
    "preserves_member_family": "heterogeneous_member_targets",
    "preserves_compound_subject": "compound_subject_targets",
    "preserves_independent_clocks": "independent_designation_clocks",
    "preserves_dependency_binding": "dependency_binding_edges",
    "preserves_set_lifecycle": "independent_set_lifecycle",
    "preserves_member_attributes": "designation_member_attributes",
    "treats_union_as_derived": "derived_union_geometry",
    "preserves_authority_snapshot": "authority_snapshot_provenance",
}

STEWARDSHIP_ORACLE_FIELDS = {
    "separates_authority_scope": "authority_scope_separation",
    "enforces_family_admission": "family_admission_posture",
    "separates_identity_publication": "identity_publication_separation",
    "preserves_public_resolution": "persistent_public_resolution",
    "supports_temporal_identifier_network": "temporal_identifier_network",
    "covers_admin_water_world": "admin_water_world_partition",
    "derives_release_scale_hints": "release_scale_hint",
    "derives_shaped_sibling_area_depth": "shaped_sibling_area_depth",
    "isolates_customer_world_branches": "customer_world_branching",
    "pins_family_authority": "family_authority_selection",
    "declares_geometry_distribution": "geometry_distribution_profile",
    "reproduces_confidence_supersession": "confidence_supersession_evidence",
    "preserves_multiaxial_time": "multiaxial_time_provenance",
    "supports_pinnable_release": "pinnable_geography_release",
    "hashes_artifacts_not_referents": "artifact_referent_separation",
    "preserves_relationship_provenance": "relationship_method_provenance",
    "guards_same_as": "same_as_evidence_gate",
    "prefers_direct_crosswalk": "direct_crosswalk_precedence",
    "declares_pack_projection": "explicit_pack_projection",
}

DOCTRINE_RULE_KEYS = (
    "normalization",
    "declared_family_precedence",
    "namespace_resolution",
    "admin_fallback_precedence",
    "runtime_classifier_fallback",
    "heuristic_fallback",
    "unknown_identity_role",
    "unknown_first_segment_scope",
    "admin_hierarchy_eligibility",
    "parent_semantics",
    "reference_level",
    "placement_policy",
    *DESIGNATION_ORACLE_FIELDS.values(),
    *STEWARDSHIP_ORACLE_FIELDS.values(),
)

BASE_DOCTRINE_RULES: dict[str, Any] = {
    "normalization": "strip_and_uppercase",
    "declared_family_precedence": "before_namespace_registry",
    "namespace_resolution": "ordered_registry_with_named_admin_fallback",
    "admin_fallback_precedence": "last",
    "runtime_classifier_fallback": True,
    "heuristic_fallback": True,
    "unknown_identity_role": "source_alias",
    "unknown_first_segment_scope": "unknown",
    "admin_hierarchy_eligibility": "admin_families_only",
    "parent_semantics": "strict_admin_parent_else_bridge_or_not_applicable",
    "reference_level": "admin_dash_depth_clamped_0_5",
    "placement_policy": "bridge_only",
    "membership_set_representation": False,
    "heterogeneous_member_targets": False,
    "compound_subject_targets": False,
    "independent_designation_clocks": False,
    "dependency_binding_edges": False,
    "independent_set_lifecycle": False,
    "designation_member_attributes": False,
    "derived_union_geometry": False,
    "authority_snapshot_provenance": False,
    "authority_scope_separation": False,
    "family_admission_posture": False,
    "identity_publication_separation": False,
    "persistent_public_resolution": False,
    "temporal_identifier_network": False,
    "admin_water_world_partition": False,
    "release_scale_hint": False,
    "shaped_sibling_area_depth": False,
    "customer_world_branching": False,
    "family_authority_selection": False,
    "geometry_distribution_profile": False,
    "confidence_supersession_evidence": False,
    "multiaxial_time_provenance": False,
    "pinnable_geography_release": False,
    "artifact_referent_separation": False,
    "relationship_method_provenance": False,
    "same_as_evidence_gate": False,
    "direct_crosswalk_precedence": False,
    "explicit_pack_projection": False,
}

WIND_TUNNEL_CONTRACT: dict[str, str] = {
    "oracle_ownership": "doctrine_independent",
    "legacy_doctrine_expectations": "open_policy_excluded_from_scoring",
    "known_issue_semantics": "visible_debt_not_required_output",
    "raw_mode": "unscored_without_explicit_oracle.raw",
    "designation_mode": "scored_only_with_explicit_oracle.designation",
    "stewardship_mode": "scored_only_with_explicit_oracle.stewardship",
    "comparison_basis": "same_corpus_same_oracle",
    "correctness_objective": "oracle_assertions_plus_clean_case_counts",
    "simplicity_objective": "separate_complexity_vector",
    "failure_gate": "unexpected_findings_only",
}

ORACLE_STATUSES = {"verified", "provisional", "open", "unscored"}


def _stable_fingerprint(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()

DOCTRINE_DECISIONS: dict[str, list[dict[str, str]]] = {
    "present_system": [
        {
            "id": "present-001",
            "decision": "ISO3-dash fallback is early and broad.",
            "effect": "Many unknown country-prefixed strings are treated as admin/local loc_ids.",
        },
        {
            "id": "present-002",
            "decision": "Sidechains mostly depend on existing ad hoc parser exceptions.",
            "effect": "Postal, NWS, source, historical, and contested cases can fall through inconsistently.",
        },
    ],
    "proposed_changes": [
        {
            "id": "proposed-001",
            "decision": "Registry-first parsing beats broad string fallback.",
            "effect": "Known sidechains, events, grids, and source aliases are classified before admin fallback.",
        },
        {
            "id": "proposed-002",
            "decision": "Non-admin geography uses bridge/context rather than parent_id.",
            "effect": "ZCTAs, districts, watersheds, zones, and protected areas avoid fake admin hierarchy.",
        },
    ],
    "containing_loc_id": [
        {
            "id": "contain-001",
            "decision": "Spatial sibling layers can declare containing_loc_id placement.",
            "effect": "Placeable sidechains and spatial objects can be routed without becoming admin children.",
        },
        {
            "id": "contain-002",
            "decision": "reference_level is a declared depth/scale hint, not raw dash count.",
            "effect": "Lakes, forests, routes, cities, and zones can carry lookup scale separately from identity.",
        },
    ],
    "solidified_sibling_layer": [
        {
            "id": "solid-001",
            "decision": "Spatial sibling layer is the default for placeable non-admin things.",
            "effect": "loc_id, entity_id, route_id, and segment_id may all carry placement fields.",
        },
        {
            "id": "solid-002",
            "decision": "Historical and contested areas are registered temporal/claim sidechains.",
            "effect": "They stop pretending to be present admin children and stop falling to source_alias.",
        },
        {
            "id": "solid-003",
            "decision": "Crosswalks and membership sets are relationship identities.",
            "effect": "NHGIS/NUTS correspondence and Euro area membership are not ordinary loc_ids.",
        },
        {
            "id": "solid-004",
            "decision": "Country-scoped health/local/statistical sidechains beat admin fallback.",
            "effect": "Canada health regions and similar operational geographies avoid fake admin hierarchy.",
        },
        {
            "id": "solid-005",
            "decision": "Adopted city loc_ids use an explicit family token in the DaedalMap public form.",
            "effect": "A core city loc_id can look like USA-CA-CITY-LosAngeles while source codes, abbreviations, translations, and nicknames remain aliases/crosswalks.",
        },
    ],
    "designation_reference_graph": [
        {
            "id": "designation-001",
            "decision": "Program designations are membership-set identities, not replacement loc_ids.",
            "effect": "One set can reference multiple geography families, entities, or compound population subjects.",
        },
        {
            "id": "designation-002",
            "decision": "Designation validity and member geography vintage are independent clocks.",
            "effect": "A legal program generation remains reproducible when its source geography is revised.",
        },
        {
            "id": "designation-003",
            "decision": "Dependencies declare live or snapshotted binding instead of implying automatic propagation.",
            "effect": "An upstream redesignation does not silently rewrite a downstream steward's published set.",
        },
        {
            "id": "designation-004",
            "decision": "Set lifecycle is independent of member lifecycle and may end without a successor.",
            "effect": "Retired programs remain citable without retiring their tracts, counties, facilities, or other members.",
        },
        {
            "id": "designation-005",
            "decision": "Membership rows may carry typed attributes and rendered unions are derived views.",
            "effect": "Scores, tiers, subprograms, and mixed members remain primary facts instead of being baked into polygons.",
        },
    ],
    "durable_public_identity": [
        {
            "id": "durable-001",
            "decision": "Authority, geographic scope, identity promise, and publication posture are independent.",
            "effect": "A public identifier can state who controls it and what it covers without encoding either claim ambiguously in its prefix.",
        },
        {
            "id": "durable-002",
            "decision": "Family admission is explicit and retired public identifiers continue resolving.",
            "effect": "Candidate and static families avoid false durability while issued identities remain safe to persist.",
        },
        {
            "id": "durable-003",
            "decision": "Identifiers are time-bounded graph assertions rather than one permanently winning string.",
            "effect": "Several identifiers can reach one referent, and a reused identifier can reach different referents only in explicit non-overlapping validity windows.",
        },
        {
            "id": "durable-004",
            "decision": "Effective, publication, and adoption time remain separate.",
            "effect": "Users can distinguish real-world validity from source and DaedalMap knowledge time.",
        },
        {
            "id": "durable-005",
            "decision": "Artifact revisions do not replace the identity of the represented referent.",
            "effect": "Geometry and crosswalk hashes may change without turning a place into a new place.",
        },
        {
            "id": "durable-006",
            "decision": "Release pinning and advanced relationship/pack policy remain out of scope for this profile.",
            "effect": "The experiment measures whether a narrow persistence contract is sufficient by itself.",
        },
        {
            "id": "durable-007",
            "decision": "The official world fabric is partitioned by administrative land coverage plus adopted ocean and major-lake water coverage.",
            "effect": "Every point has explicit land or water context without fabricating administrative descendants where a tier is absent.",
        },
        {
            "id": "durable-008",
            "decision": "Customer worlds are isolated branches and affect the official world only through explicit reviewed promotion.",
            "effect": "Customers can define independent identities and geometry without collisions or cross-world leakage; consolidation occurs at merge time.",
        },
        {
            "id": "durable-009",
            "decision": "Each official reference family selects and pins a named authority and source release.",
            "effect": "DaedalMap can explain its official view without pretending to be neutral or falling back to a universal latest-source-wins rule.",
        },
    ],
    "reproducible_relationship_graph": [
        {
            "id": "repro-001",
            "decision": "Geography releases are pinnable dependency manifests.",
            "effect": "An analysis can replay the namespace, geometry, crosswalk, membership, and source artifacts it used.",
        },
        {
            "id": "repro-002",
            "decision": "Relationship edges carry method, source, and reproducibility metadata.",
            "effect": "Asserted, derived, expert-judgment, and unreproducible relationships remain distinguishable.",
        },
        {
            "id": "repro-003",
            "decision": "same_as is allowed only with sourced identity evidence.",
            "effect": "Geometric similarity and convenient crosswalks cannot silently become identity equivalence.",
        },
        {
            "id": "repro-004",
            "decision": "Direct authoritative crosswalks beat lossy admin-pivot inference.",
            "effect": "Published many-to-many relationships retain their weights and semantics.",
        },
        {
            "id": "repro-005",
            "decision": "Historical packs declare source-era geography or an explicit present allocation.",
            "effect": "Reproduction does not depend on an undocumented projection into current loc_ids.",
        },
        {
            "id": "repro-006",
            "decision": "Public persistence guarantees remain out of scope for this profile.",
            "effect": "The experiment isolates translation and replay behavior from durable-identity policy.",
        },
        {
            "id": "repro-007",
            "decision": "Non-shaped normalized scale is a release-versioned presentation and query hint, never geographic identity.",
            "effect": "Zoom, labeling, aggregation, and comparison can improve for grids, routes, and source aliases without changing their identifiers.",
        },
        {
            "id": "repro-008",
            "decision": "Geometry packages declare their own access, precision, generalization, attribution, privacy, and world scope.",
            "effect": "Data and geometry can share a download envelope without inheriting one another's distribution policy.",
        },
        {
            "id": "repro-009",
            "decision": "Confidence and supersession are typed, nullable, source-backed, and reproducible by method and release.",
            "effect": "A candidate never becomes a confirmed successor through a default score or undocumented threshold change.",
        },
        {
            "id": "repro-010",
            "decision": "A shaped country sibling's complete owned physical area determines canonical ancestry depth against a stable-spine-fingerprint-pinned country profile.",
            "effect": "Area controls precision while official ownership selects extent, dominant same-depth overlap selects one anchor, and every crossing remains a bridge.",
        },
    ],
    "stewarded_release_graph": [
        {
            "id": "steward-001",
            "decision": "Authority, geographic scope, identity promise, and publication posture are independent fields.",
            "effect": "A nationally scoped private or civic product does not impersonate a national government namespace.",
        },
        {
            "id": "steward-002",
            "decision": "Families graduate through an explicit admission posture backed by stewardship and release evidence.",
            "effect": "Static and candidate products remain usable without receiving an unsupported durability promise.",
        },
        {
            "id": "steward-003",
            "decision": "An issued public identity resolves after retirement through a tombstone or successor record.",
            "effect": "Persisted loc_ids and aliases never become unexplained 404s.",
        },
        {
            "id": "steward-004",
            "decision": "Identifier-to-referent assertions carry validity windows; the graph is durable even when preferred identifiers change.",
            "effect": "Aliases, source codes, and DaedalMap identifiers can all be entry points without silent code reuse or a permanent single-string winner.",
        },
        {
            "id": "steward-005",
            "decision": "Effective, publication, and DaedalMap adoption time are recorded separately.",
            "effect": "Legal truth, source knowledge, and platform knowledge are reproducible without overloading valid_from.",
        },
        {
            "id": "steward-006",
            "decision": "A pinnable geography release names versioned namespace, geometry, crosswalk, and membership artifacts.",
            "effect": "An analysis can replay the exact geographic interpretation layer it used.",
        },
        {
            "id": "steward-007",
            "decision": "Hashes identify artifacts, never real-world referents.",
            "effect": "Geometry or crosswalk revisions move artifact hashes without silently replacing geographic identity.",
        },
        {
            "id": "steward-008",
            "decision": "Relationship edges carry method, source, reproducibility, and guarded identity equivalence.",
            "effect": "Expert judgment, direct crosswalks, and same_as claims remain distinguishable and auditable.",
        },
        {
            "id": "steward-009",
            "decision": "Historical packs declare source-era geography or an explicit present-day allocation.",
            "effect": "A present loc_id projection cannot silently replace the geography in which a source observation was published.",
        },
        {
            "id": "steward-010",
            "decision": "Administrative land and adopted ocean or major-lake water coverage form a gap-free official world partition.",
            "effect": "Global point resolution exposes gaps, overlaps, coast policy, and explicit null administrative tiers rather than hiding them.",
        },
        {
            "id": "steward-011",
            "decision": "Non-shaped presentation scale hints name their purpose, method, input release, and output release and never affect identity.",
            "effect": "A builder revision can change map behavior for grids, routes, and source aliases without silently changing identity.",
        },
        {
            "id": "steward-012",
            "decision": "Every private identity is scoped by world and branch, and official promotion is a reviewed merge operation.",
            "effect": "Identical local strings can coexist safely while authority, license, provenance, lifecycle, and geometry conflicts remain visible at merge.",
        },
        {
            "id": "steward-013",
            "decision": "Official family authority is deterministic, release-pinned, cited, and separate from preserved alternate claims.",
            "effect": "Country, water, administrative, and other families can follow different responsible authorities while remaining reproducible.",
        },
        {
            "id": "steward-014",
            "decision": "Every downloadable geometry bundle carries one explicit geometry distribution profile.",
            "effect": "Public generalized and customer exact geometry can use the same machinery while validating different access and export promises.",
        },
        {
            "id": "steward-015",
            "decision": "Confidence and supersession claims pin method, source, algorithm, threshold, evidence artifact, and release.",
            "effect": "Authoritative claims may honestly omit a numeric score while probabilistic candidates remain distinguishable from confirmed successors.",
        },
        {
            "id": "steward-016",
            "decision": "Shaped country siblings use ISO3-owned, physical-area-derived canonical ancestry pinned to the adopted spine fingerprint.",
            "effect": "Large shapes receive shorter ancestry and small shapes longer ancestry; boundary straddling changes bridges and anchor choice, not depth.",
        },
    ],
}

PROPOSED_NAMESPACE_REGISTRY: list[dict[str, Any]] = [
    {
        "namespace": "current_admin_iso3",
        "pattern": r"^[A-Z]{3}$",
        "identity_role": "loc_id",
        "family_id": "admin_0",
        "scope_type": "admin_country",
        "public_promise": "stable_public_loc_id",
        "raw_input_allowed": True,
        "canonical_output_allowed": True,
        "bridge_policy": "admin_spine",
        "lifecycle_policy": "current_with_supersession",
        "license_policy": "public",
    },
    {
        "namespace": "country_shaped_sibling_area_depth",
        "pattern": r"^[A-Z]{3}(?:-[A-Z0-9]+)*-(?:POSTAL|INDIGENOUS|WEATHER|FIREWX|PLACE|URBAN|ELECTORAL|SCHOOL|HEALTH|WATERSHED|PROTECTED|WATER|ECOLOGICAL|TIMEZONE|PROGRAM)-[A-Z0-9][A-Z0-9-]*$",
        "identity_role": "loc_id",
        "family_id": "shaped_sidechain",
        "scope_type": "country_reference_scope",
        "public_promise": "stable_public_loc_id",
        "raw_input_allowed": True,
        "canonical_output_allowed": True,
        "bridge_policy": "sibling_area_depth_and_overlap",
        "lifecycle_policy": "source_vintage_with_alias_lifecycle",
        "license_policy": "family_specific",
    },
    {
        "namespace": "current_admin_local",
        "pattern": r"^[A-Z]{3}(?:-[A-Z0-9]+)+$",
        "identity_role": "loc_id",
        "family_id": "admin_local",
        "scope_type": "admin_hierarchy",
        "public_promise": "stable_public_alias",
        "raw_input_allowed": True,
        "canonical_output_allowed": True,
        "bridge_policy": "admin_spine_or_country_crosswalk",
        "lifecycle_policy": "current_with_alias_lifecycle",
        "license_policy": "public",
    },
    {
        "namespace": "geoboundaries_storage",
        "pattern": r"^[A-Z]{3}(?:-G[A-Z0-9]+)+$",
        "identity_role": "loc_id",
        "family_id": "admin_geometry",
        "scope_type": "admin_hierarchy",
        "public_promise": "canonical_storage_identity",
        "raw_input_allowed": True,
        "canonical_output_allowed": False,
        "bridge_policy": "admin_spine_storage",
        "lifecycle_policy": "geometry_bank_lifecycle",
        "license_policy": "public",
    },
    {
        "namespace": "usa_zcta",
        "pattern": r"^USA-Z-\d{5}$",
        "identity_role": "loc_id",
        "family_id": "overlay_zcta",
        "scope_type": "country_reference_scope",
        "public_promise": "stable_public_loc_id",
        "raw_input_allowed": True,
        "canonical_output_allowed": True,
        "bridge_policy": "admin_overlap",
        "lifecycle_policy": "source_vintage",
        "license_policy": "public",
    },
    {
        "namespace": "country_postal_sidechain",
        "pattern": r"^[A-Z]{3}-(?:FSA|POA|PC)-[A-Z0-9]+$",
        "identity_role": "loc_id",
        "family_id": "postal",
        "scope_type": "country_reference_scope",
        "public_promise": "resolver_or_family_specific",
        "raw_input_allowed": True,
        "canonical_output_allowed": False,
        "bridge_policy": "family_specific",
        "lifecycle_policy": "source_vintage",
        "license_policy": "family_specific",
    },
    {
        "namespace": "country_scoped_sidechain",
        "pattern": r"^[A-Z]{3}-(?:TRIBAL|NWSZ|NWSFZ|HUC\d*|CD\d*|SD|UA\d*|CITY|MUNI|FOREST|PARK|FEMA|POWER|FED|CPCAD|TREATY)[A-Z0-9-]*$",
        "identity_role": "loc_id",
        "family_id": "sidechain",
        "scope_type": "country_reference_scope",
        "public_promise": "family_specific",
        "raw_input_allowed": True,
        "canonical_output_allowed": False,
        "bridge_policy": "family_specific",
        "lifecycle_policy": "family_specific",
        "license_policy": "family_specific",
    },
    {
        "namespace": "source_family_sidechain",
        "pattern": r"^(?:EEZ|HYBAS|HYDROLAKES|IHO1953|MRGID|WDPA|WWF-ECO|MRGID-EEZ|FOREST|URBAN)-[A-Z0-9-]+$",
        "identity_role": "loc_id",
        "family_id": "source_sidechain",
        "scope_type": "source_family_scope",
        "public_promise": "family_specific",
        "raw_input_allowed": True,
        "canonical_output_allowed": False,
        "bridge_policy": "family_specific",
        "lifecycle_policy": "source_vintage",
        "license_policy": "family_specific",
    },
    {
        "namespace": "external_source_alias",
        "pattern": r"^(?:OSM|GADM|WIKIDATA|GEONAMES|CGNDB|UNLOCODE|ISO3166-3|COW|FCC|PLACEKEY|WHG|GERS|OCHA-PCODE|OS-UPRN|PMTILES|TILE-ZXY)-.+$",
        "identity_role": "source_alias",
        "family_id": "source_alias",
        "scope_type": "source_family_scope",
        "public_promise": "source_alias_only",
        "raw_input_allowed": True,
        "canonical_output_allowed": False,
        "bridge_policy": "reviewed_alias_or_relationship",
        "lifecycle_policy": "source_lifecycle",
        "license_policy": "source_specific",
    },
    {
        "namespace": "grid_or_tile",
        "pattern": r"^(?:H3|S2|OLC|PLUSCODE|MGRS|QUADKEY|LANDSAT|SENTINEL2|GHSL|OGC-TILE|RASTER|PLACEKEY-@)-.+$",
        "identity_role": "grid_id",
        "family_id": "grid",
        "scope_type": "grid_scope",
        "public_promise": "source_alias_only",
        "raw_input_allowed": True,
        "canonical_output_allowed": False,
        "bridge_policy": "grid_overlap",
        "lifecycle_policy": "source_grid_version",
        "license_policy": "source_specific",
    },
    {
        "namespace": "event_or_forecast",
        "pattern": r"^(?:EQ|FIRE|FLOOD|HRCN|TORN|TSUN|VOLC|NHC|NWS|GFM)(?:-|:).+$",
        "identity_role": "event_id",
        "family_id": "event",
        "scope_type": "source_family_scope",
        "public_promise": "event_identity",
        "raw_input_allowed": True,
        "canonical_output_allowed": False,
        "bridge_policy": "event_affected_area",
        "lifecycle_policy": "event_time_window",
        "license_policy": "source_specific",
    },
    {
        "namespace": "network_or_route",
        "pattern": r"^(?:ROUTE|ROAD|TRAIL|RIVER|HYDRORIVERS|SEGMENT|REACH|WAY|LINE|UN-LOC).+$",
        "identity_role": "segment_id",
        "family_id": "network_segment",
        "scope_type": "source_family_scope",
        "public_promise": "source_alias_only",
        "raw_input_allowed": True,
        "canonical_output_allowed": False,
        "bridge_policy": "network_intersection",
        "lifecycle_policy": "network_version",
        "license_policy": "source_specific",
    },
    {
        "namespace": "historical_or_claim_area",
        "pattern": r"^(?:CSHAPES|AHCB|CLAIM|NE-DISPUTED|UN-ABYEI|EUROAREA)-.+$",
        "identity_role": "loc_id",
        "family_id": "temporal_or_claim_sidechain",
        "scope_type": "source_family_scope",
        "public_promise": "internal_candidate_identity",
        "raw_input_allowed": True,
        "canonical_output_allowed": False,
        "bridge_policy": "temporal_or_claim_crosswalk",
        "lifecycle_policy": "validity_window",
        "license_policy": "source_specific",
    },
    {
        "namespace": "crosswalk_artifact",
        "pattern": r"^(?:NHGIS-XWALK|NUTS-XWALK|STATCAN-XWALK|ABS-XWALK|ONS-XWALK|REL-REVIEW)-.+$",
        "identity_role": "crosswalk_id",
        "family_id": "relationship",
        "scope_type": "source_family_scope",
        "public_promise": "source_alias_only",
        "raw_input_allowed": True,
        "canonical_output_allowed": False,
        "bridge_policy": "versioned_crosswalk",
        "lifecycle_policy": "artifact_version",
        "license_policy": "source_specific",
    },
]

SOLIDIFIED_SIBLING_LAYER_REGISTRY: list[dict[str, Any]] = [
    {
        **entry,
        "pattern": r"^[A-Z]{3}(?:-[A-Z0-9]{2,3})?-(?:HA|CLHA|LHA|HEALTH|CITY|MUNI|PLACE|Z|ZCTA|FSA|POA|PC|TRIBAL|NWSZ|NWSFZ|HUC\d*|CD\d*|SD|UA\d*|FOREST|PARK|FEMA|POWER|FED|CPCAD|TREATY|NHGIS)[A-Z0-9-]*$",
        "scope_type": "country_reference_scope",
        "bridge_policy": "sibling_layer_placement",
    }
    if entry["namespace"] == "country_scoped_sidechain"
    else {
        **entry,
        "pattern": r"^(?:EEZ|HYBAS|HYDROLAKES|IHO1953|MRGID|WDPA|WWF-ECO|MRGID-EEZ|FOREST|URBAN|CSHAPES|AHCB|CLAIM|NE-DISPUTED|UN-ABYEI)-[A-Z0-9-]+$",
        "family_id": "source_or_temporal_sidechain",
        "bridge_policy": "sibling_layer_placement_or_temporal_crosswalk",
    }
    if entry["namespace"] == "source_family_sidechain"
    else {
        **entry,
        "pattern": r"^(?:NHGIS-XWALK|NUTS-XWALK|STATCAN-XWALK|ABS-XWALK|ONS-XWALK|REL-REVIEW|EUROAREA|COW-STATE)-.+$",
        "identity_role": "relationship_id",
        "family_id": "relationship",
        "bridge_policy": "versioned_relationship",
    }
    if entry["namespace"] == "crosswalk_artifact"
    else {
        **entry,
        "pattern": r"^(?:(?:OSM|GADM|WIKIDATA|GEONAMES|CGNDB|UNLOCODE|ISO3166-3|COW|FCC|WHG|OCHA-PCODE|OS-UPRN|PMTILES|TILE-ZXY)-.+|PLACEKEY-(?!@).+|GERS-.+)$",
    }
    if entry["namespace"] == "external_source_alias"
    else entry
    for entry in PROPOSED_NAMESPACE_REGISTRY
    if entry["namespace"] != "historical_or_claim_area"
]

DESIGNATION_REFERENCE_GRAPH_REGISTRY: list[dict[str, Any]] = [
    *SOLIDIFIED_SIBLING_LAYER_REGISTRY,
    {
        "namespace": "designation_membership_set",
        "pattern": r"^(?:[A-Z0-9]+-)*DESIG-[A-Z0-9-]+$",
        "identity_role": "membership_set_id",
        "family_id": "membership_set",
        "scope_type": "authority_scope",
        "public_promise": "source_alias_only",
        "raw_input_allowed": True,
        "canonical_output_allowed": False,
        "bridge_policy": "typed_membership_graph",
        "lifecycle_policy": "designation_generation",
        "license_policy": "source_specific",
    },
]

STEWARDED_RELEASE_GRAPH_REGISTRY: list[dict[str, Any]] = [
    *DESIGNATION_REFERENCE_GRAPH_REGISTRY,
]

DURABLE_PUBLIC_IDENTITY_REGISTRY: list[dict[str, Any]] = [
    *DESIGNATION_REFERENCE_GRAPH_REGISTRY,
]

REPRODUCIBLE_RELATIONSHIP_GRAPH_REGISTRY: list[dict[str, Any]] = [
    *DESIGNATION_REFERENCE_GRAPH_REGISTRY,
]

PRESENT_SYSTEM_REGISTRY: list[dict[str, Any]] = [
    {
        "namespace": "current_admin_iso3",
        "pattern": r"^[A-Z]{3}$",
        "identity_role": "loc_id",
        "family_id": "admin_0",
        "scope_type": "admin_country",
        "public_promise": "stable_public_loc_id",
    },
    {
        "namespace": "current_admin_local",
        "pattern": r"^[A-Z]{3}(?:-[A-Z0-9]+)+$",
        "identity_role": "loc_id",
        "family_id": "admin_local",
        "scope_type": "admin_hierarchy",
        "public_promise": "stable_public_alias",
    },
    {
        "namespace": "geoboundaries_storage",
        "pattern": r"^[A-Z]{3}(?:-G[A-Z0-9]+)+$",
        "identity_role": "loc_id",
        "family_id": "admin_geometry",
        "scope_type": "admin_hierarchy",
        "public_promise": "canonical_storage_identity",
    },
    {
        "namespace": "known_grid",
        "pattern": r"^(?:H3|S2|OLC|PLUSCODE|MGRS|QUADKEY|LANDSAT|SENTINEL2|GHSL|OGC-TILE|RASTER)-.+$",
        "identity_role": "grid_id",
        "family_id": "grid",
        "scope_type": "grid_scope",
        "public_promise": "source_alias_only",
    },
    {
        "namespace": "known_event",
        "pattern": r"^(?:EQ|FIRE|FLOOD|HRCN|TORN|TSUN|VOLC|NHC|NWS|GFM)(?:-|:).+$",
        "identity_role": "event_id",
        "family_id": "event",
        "scope_type": "source_family_scope",
        "public_promise": "event_identity",
    },
]

DOCTRINE_PROFILES: dict[str, dict[str, Any]] = {
    "present_system": {
        "description": "Broad current runtime-style parsing where ISO3-dash strings tend to become admin/local loc_ids.",
        "registry": PRESENT_SYSTEM_REGISTRY,
        "rules": {
            **BASE_DOCTRINE_RULES,
            "admin_fallback_precedence": "first",
            "placement_policy": "parent_id",
        },
    },
    "proposed_changes": {
        "description": "Registry-first present admin spine with explicit sidechain/source/entity/event/grid roles.",
        "registry": PROPOSED_NAMESPACE_REGISTRY,
        "rules": {
            **BASE_DOCTRINE_RULES,
            "admin_fallback_precedence": "last",
            "placement_policy": "bridge_only",
        },
    },
    "containing_loc_id": {
        "description": "Registry-first doctrine where every location-like family may declare reference_level and containing_loc_id placement without becoming admin hierarchy.",
        "registry": PROPOSED_NAMESPACE_REGISTRY,
        "rules": {
            **BASE_DOCTRINE_RULES,
            "admin_fallback_precedence": "last",
            "placement_policy": "containing_loc_id",
        },
    },
    "solidified_sibling_layer": {
        "description": "Next-pass doctrine that solidifies spatial sibling placement, temporal/claim sidechains, relationship artifacts, and country-scoped sidechains before admin fallback.",
        "registry": SOLIDIFIED_SIBLING_LAYER_REGISTRY,
        "rules": {
            **BASE_DOCTRINE_RULES,
            "admin_fallback_precedence": "last",
            "placement_policy": "containing_loc_id",
            "membership_set_representation": True,
        },
    },
    "designation_reference_graph": {
        "description": "Solidified sibling-layer doctrine plus typed, versioned, provenance-aware program designation membership sets.",
        "registry": DESIGNATION_REFERENCE_GRAPH_REGISTRY,
        "rules": {
            **BASE_DOCTRINE_RULES,
            "admin_fallback_precedence": "last",
            "placement_policy": "containing_loc_id",
            "membership_set_representation": True,
            "heterogeneous_member_targets": True,
            "compound_subject_targets": True,
            "independent_designation_clocks": True,
            "dependency_binding_edges": True,
            "independent_set_lifecycle": True,
            "designation_member_attributes": True,
            "derived_union_geometry": True,
            "authority_snapshot_provenance": True,
        },
    },
    "durable_public_identity": {
        "description": "Designation reference graph plus the minimum public persistence contract, without release-lockfile or advanced relationship policy.",
        "registry": DURABLE_PUBLIC_IDENTITY_REGISTRY,
        "rules": {
            **BASE_DOCTRINE_RULES,
            "admin_fallback_precedence": "last",
            "placement_policy": "containing_loc_id",
            "membership_set_representation": True,
            "heterogeneous_member_targets": True,
            "compound_subject_targets": True,
            "independent_designation_clocks": True,
            "dependency_binding_edges": True,
            "independent_set_lifecycle": True,
            "designation_member_attributes": True,
            "derived_union_geometry": True,
            "authority_snapshot_provenance": True,
            "authority_scope_separation": True,
            "family_admission_posture": True,
            "identity_publication_separation": True,
            "persistent_public_resolution": True,
            "temporal_identifier_network": True,
            "admin_water_world_partition": True,
            "customer_world_branching": True,
            "family_authority_selection": True,
            "multiaxial_time_provenance": True,
            "artifact_referent_separation": True,
        },
    },
    "reproducible_relationship_graph": {
        "description": "Designation reference graph plus release replay, relationship evidence, crosswalk precedence, and explicit historical-pack projection, without public persistence policy.",
        "registry": REPRODUCIBLE_RELATIONSHIP_GRAPH_REGISTRY,
        "rules": {
            **BASE_DOCTRINE_RULES,
            "admin_fallback_precedence": "last",
            "placement_policy": "containing_loc_id",
            "membership_set_representation": True,
            "heterogeneous_member_targets": True,
            "compound_subject_targets": True,
            "independent_designation_clocks": True,
            "dependency_binding_edges": True,
            "independent_set_lifecycle": True,
            "designation_member_attributes": True,
            "derived_union_geometry": True,
            "authority_snapshot_provenance": True,
            "pinnable_geography_release": True,
            "release_scale_hint": True,
            "shaped_sibling_area_depth": True,
            "geometry_distribution_profile": True,
            "confidence_supersession_evidence": True,
            "relationship_method_provenance": True,
            "same_as_evidence_gate": True,
            "direct_crosswalk_precedence": True,
            "explicit_pack_projection": True,
        },
    },
    "stewarded_release_graph": {
        "description": "Designation reference graph plus explicit stewardship, persistence, provenance, and reproducible geography-release contracts.",
        "registry": STEWARDED_RELEASE_GRAPH_REGISTRY,
        "rules": {
            **BASE_DOCTRINE_RULES,
            "admin_fallback_precedence": "last",
            "placement_policy": "containing_loc_id",
            "membership_set_representation": True,
            "heterogeneous_member_targets": True,
            "compound_subject_targets": True,
            "independent_designation_clocks": True,
            "dependency_binding_edges": True,
            "independent_set_lifecycle": True,
            "designation_member_attributes": True,
            "derived_union_geometry": True,
            "authority_snapshot_provenance": True,
            **{rule_key: True for rule_key in STEWARDSHIP_ORACLE_FIELDS.values()},
        },
    },
}

NAMESPACE_REGISTRY = PROPOSED_NAMESPACE_REGISTRY


def _clean(value: Any) -> str:
    return str(value or "").strip().upper()


def _parts(value: str) -> list[str]:
    return [part for part in _clean(value).split("-") if part]


def _looks_like_country_scoped_sidechain(value: str) -> bool:
    text = _clean(value)
    return any(pattern.fullmatch(text) for pattern in COUNTRY_SCOPED_SIDECHAIN_PATTERNS)


def _profile(doctrine: str | None = None) -> dict[str, Any]:
    return DOCTRINE_PROFILES.get(str(doctrine or "proposed_changes"), DOCTRINE_PROFILES["proposed_changes"])


def _rule(doctrine: str | None, key: str) -> Any:
    profile = _profile(doctrine)
    rules = profile.get("rules") or {}
    if key not in rules:
        raise ValueError(f"doctrine {doctrine or 'proposed_changes'} does not declare rule {key!r}")
    return rules[key]


def doctrine_decisions(doctrine: str | None = None) -> list[dict[str, str]]:
    """Return the explicit policy decisions attached to a doctrine profile."""
    return list(DOCTRINE_DECISIONS.get(str(doctrine or "proposed_changes"), []))


def lookup_namespace(identifier: str | None, *, doctrine: str | None = None) -> dict[str, Any] | None:
    """Return the first registry entry that matches a raw identifier."""
    value = _clean(identifier)
    if not value:
        return None
    profile = _profile(doctrine)
    registry = profile["registry"]
    admin_fallback_precedence = str(_rule(doctrine, "admin_fallback_precedence"))
    fallback: dict[str, Any] | None = None
    for entry in registry:
        if re.fullmatch(str(entry["pattern"]), value):
            if entry["namespace"] == "current_admin_local" and admin_fallback_precedence == "last":
                fallback = entry
                continue
            return entry
    return fallback


def infer_identity_role(identifier: str | None, *, family_id: str | None = None, doctrine: str | None = None) -> str:
    """Return the smallest honest identity role for a candidate identifier."""
    value = _clean(identifier)
    family = _clean(family_id).lower()
    parts = _parts(value)

    def declared_family_role() -> str | None:
        if family in ADMIN_FAMILIES or family in SIDECHAIN_FAMILIES:
            return "loc_id"
        if family in {"entity", "entity_point", "entity_area"}:
            return "entity_id"
        if family == "event":
            return "event_id"
        if family in {"route", "network_route"}:
            return "route_id"
        if family in {"segment", "reach", "network_segment"}:
            return "segment_id"
        if family in {"grid", "raster", "cell"}:
            return "grid_id"
        if family in {"membership_set", "designation_set"}:
            return "membership_set_id"
        if family == "source_alias":
            return "source_alias"
        return None

    family_precedence = str(_rule(doctrine, "declared_family_precedence"))
    if family_precedence == "before_namespace_registry":
        family_role = declared_family_role()
        if family_role:
            return family_role

    registry = lookup_namespace(value, doctrine=doctrine)
    if registry:
        return str(registry["identity_role"])

    if family_precedence == "after_namespace_registry":
        family_role = declared_family_role()
        if family_role:
            return family_role

    if _rule(doctrine, "runtime_classifier_fallback"):
        loc_family = classify_loc_id_family(value)
        if loc_family in ADMIN_FAMILIES or loc_family in SIDECHAIN_FAMILIES:
            return "loc_id"
        if loc_family == "event_or_entity":
            return "event_id"

    if _rule(doctrine, "heuristic_fallback"):
        if _looks_like_country_scoped_sidechain(value):
            return "loc_id"
        if parts and (parts[0] in GRID_PREFIXES or any(part in GRID_PREFIXES for part in parts[:2])):
            return "grid_id"
        if parts and (parts[0] in ROUTE_PREFIXES):
            return "route_id"
        if parts and (parts[0] in SEGMENT_PREFIXES or parts[0] in {"HYDRORIVERS"}):
            return "segment_id"
        if any(part in EVENT_MARKERS for part in parts):
            return "event_id"
    return str(_rule(doctrine, "unknown_identity_role"))


def infer_first_segment_scope(identifier: str | None, *, family_id: str | None = None, doctrine: str | None = None) -> str | None:
    """Classify what the first loc_id segment is allowed to mean."""
    value = _clean(identifier)
    if not value:
        return None
    first = value.split("-", 1)[0]
    family = _clean(family_id).lower()
    if re.fullmatch(r"[A-Z]{3}", value):
        return "admin_country"
    registry = lookup_namespace(value, doctrine=doctrine)
    if registry and family not in ADMIN_FAMILIES:
        return str(registry["scope_type"])
    if first in SOURCE_FAMILY_PREFIXES or value.startswith("WWF-ECO-"):
        return "source_family_scope"
    country_scoped_match = re.match(r"^([A-Z]{3})-", value)
    if family in {"grid", "raster", "cell"}:
        return "grid_scope"
    if family in {"route", "network_route", "segment", "reach", "network_segment"} and re.match(r"^[A-Z]{3}-", value):
        return "country_reference_scope"
    if family in SIDECHAIN_FAMILIES and (
        _looks_like_country_scoped_sidechain(value)
        or (country_scoped_match is not None and first == country_scoped_match.group(1))
    ):
        return "country_reference_scope"
    if family in ADMIN_FAMILIES or classify_loc_id_family(value) in ADMIN_FAMILIES:
        return "admin_hierarchy"
    if _looks_like_country_scoped_sidechain(value):
        return "country_reference_scope"
    if first in GRID_PREFIXES:
        return "grid_scope"
    return str(_rule(doctrine, "unknown_first_segment_scope"))


def loc_id_may_encode_admin_hierarchy(identifier: str | None, *, family_id: str | None = None, doctrine: str | None = None) -> bool:
    registry = lookup_namespace(identifier, doctrine=doctrine)
    family = _clean(family_id).lower() or (str(registry.get("family_id")) if registry else None) or classify_loc_id_family(identifier)
    return family in ADMIN_FAMILIES


def expected_parent_semantics(identifier: str | None, *, family_id: str | None = None, doctrine: str | None = None) -> str:
    registry = lookup_namespace(identifier, doctrine=doctrine)
    if registry and registry.get("identity_role") in {"relationship_id", "crosswalk_id", "membership_set_id"}:
        return "not_applicable"
    family = _clean(family_id).lower() or (str(registry.get("family_id")) if registry else None) or classify_loc_id_family(identifier)
    if family in ADMIN_FAMILIES:
        return "strict_admin_parent"
    if family in SIDECHAIN_FAMILIES or family in {
        "sidechain",
        "shaped_sidechain",
        "source_sidechain",
        "source_or_temporal_sidechain",
        "temporal_or_claim_sidechain",
        "historical_admin",
        "historical_statistical_area",
        "temporal_membership_area",
        "contested_admin",
        "claim_area",
        "boundary_line",
    }:
        return "context_or_bridge_only"
    return "not_applicable"


def infer_admin_reference_level(identifier: str | None, *, family_id: str | None = None, doctrine: str | None = None) -> str | None:
    """Infer the admin-spine label depth when the identifier is truly admin."""
    if not loc_id_may_encode_admin_hierarchy(identifier, family_id=family_id, doctrine=doctrine):
        return None
    depth = max(0, min(len(_parts(identifier)) - 1, 5))
    return f"label_{depth}"


def expected_placement_semantics(identifier: str | None, *, family_id: str | None = None, doctrine: str | None = None) -> str:
    parent_semantics = expected_parent_semantics(identifier, family_id=family_id, doctrine=doctrine)
    if parent_semantics == "strict_admin_parent":
        return "identity_parent"
    placement_policy = str(_rule(doctrine, "placement_policy"))
    if placement_policy == "containing_loc_id" and infer_identity_role(identifier, family_id=family_id, doctrine=doctrine) in SPATIALLY_PLACEABLE_ROLES:
        return "containing_loc_id"
    if parent_semantics == "context_or_bridge_only":
        return "bridge_or_context"
    return "not_applicable"


def _raw_case(case: dict[str, Any]) -> dict[str, Any]:
    """Return raw-input metadata for compatibility with older callers.

    New dual-mode evaluation keeps the original case and selects ``oracle.raw``
    explicitly. Doctrine-specific expectations are always removed because they
    describe a candidate policy, not independent test truth.
    """
    raw = dict(case)
    raw.pop("family_id", None)
    for legacy_key in ORACLE_FIELDS.values():
        raw.pop(legacy_key, None)
        raw.pop(f"{legacy_key}_by_doctrine", None)
    raw.pop("expected_issues", None)
    raw.pop("expected_issue_codes", None)
    raw.pop("expected_issues_by_doctrine", None)
    return raw


ISSUE_CODE_PREFIXES = (
    ("unknown expected_role", "ORACLE_INVALID_ROLE"),
    ("role mismatch", "ROLE_MISMATCH"),
    ("first segment scope mismatch", "SCOPE_MISMATCH"),
    ("parent semantics mismatch", "PARENT_SEMANTICS_MISMATCH"),
    ("reference level mismatch", "REFERENCE_LEVEL_MISMATCH"),
    ("placement semantics mismatch", "PLACEMENT_MISMATCH"),
    ("unknown public_promise", "INVALID_PUBLIC_PROMISE"),
    ("unknown reference_level_reason", "INVALID_REFERENCE_LEVEL_REASON"),
    ("unknown reference_level", "INVALID_REFERENCE_LEVEL"),
    ("unknown containment_method", "INVALID_CONTAINMENT_METHOD"),
    ("non-admin families must not expose admin_level", "FAKE_ADMIN_DEPTH"),
    ("non-admin parent_id", "FAKE_ADMIN_PARENT"),
    ("contested parentage", "MISSING_PARENT_CLAIMS"),
    ("missing or unverified admin parent", "INVALID_NULL_PARENT"),
    ("supersession_required", "MISSING_SUPERSESSION_LINK"),
    ("bridge_required cases", "MISSING_BRIDGE_TYPE"),
    ("containing_loc_id belongs", "PLACEMENT_POLICY_VIOLATION"),
    ("containing_loc_id requires", "MISSING_CONTAINMENT_METHOD"),
    ("cross-boundary geography", "INVALID_FULL_CONTAINMENT"),
    ("cross-boundary containing_loc_id", "MISSING_OVERLAP_CONTEXT"),
    ("admin families need", "INVALID_ADMIN_REFERENCE_REASON"),
    ("non-admin reference_level requires", "MISSING_REFERENCE_REASON"),
    ("non-admin reference_level must not", "FAKE_ADMIN_REFERENCE_REASON"),
    ("loc_id case needs", "UNREGISTERED_LOC_ID"),
)


def _issue_code(message: str) -> str:
    for prefix, code in ISSUE_CODE_PREFIXES:
        if message.startswith(prefix):
            return code
    if message.endswith("must not be persisted as loc_id"):
        return "INVALID_LOC_ID_PERSISTENCE"
    return "UNCLASSIFIED_FINDING"


def _oracle_for_case(case: dict[str, Any], *, mode: str) -> dict[str, Any]:
    """Build a doctrine-independent oracle view for one evaluation mode.

    ``oracle.declared`` and ``oracle.raw`` are the preferred schema. Existing
    flat ``expected_*`` fields remain a compatibility source for declared mode.
    Any field with a ``*_by_doctrine`` override is treated as an open policy
    question and excluded from scoring until it is moved into the oracle.
    """
    explicit_root = case.get("oracle") or {}
    explicit = explicit_root.get(mode) if isinstance(explicit_root, dict) else None
    expectations: dict[str, Any] = {}
    open_policy_fields: list[str] = []
    known_issue_messages: list[str] = []
    known_issue_codes: list[str] = []
    policy_options: dict[str, Any] = {}
    source = "none"
    status = "unscored"

    if isinstance(explicit, dict):
        source = "explicit"
        status = str(explicit.get("status") or "verified")
        for result_key, legacy_key in ORACLE_FIELDS.items():
            if result_key in explicit:
                expectations[result_key] = explicit[result_key]
            elif legacy_key in explicit:
                expectations[result_key] = explicit[legacy_key]
        known_issue_messages = [str(value) for value in explicit.get("known_issues") or []]
        known_issue_codes = [str(value) for value in explicit.get("known_issue_codes") or []]
        open_policy_fields = [str(value) for value in explicit.get("open_policy_fields") or []]
        policy_options = dict(explicit.get("policy_options") or {})
    elif mode == "declared":
        source = "legacy_flat"
        status = "provisional"
        for result_key, legacy_key in ORACLE_FIELDS.items():
            if case.get(f"{legacy_key}_by_doctrine"):
                open_policy_fields.append(result_key)
            elif legacy_key in case:
                expectations[result_key] = case.get(legacy_key)
        known_issue_messages = [str(value) for value in case.get("expected_issues") or []]
        known_issue_codes = [str(value) for value in case.get("expected_issue_codes") or []]

    if status in {"open", "unscored"}:
        expectations = {}
    for field in open_policy_fields:
        expectations.pop(field, None)
    return {
        "mode": mode,
        "source": source,
        "status": status,
        "expectations": expectations,
        "known_issue_messages": known_issue_messages,
        "known_issue_codes": known_issue_codes,
        "open_policy_fields": sorted(set(open_policy_fields)),
        "policy_options": policy_options,
        "scored": bool(expectations),
    }


def _expected_value(oracle: dict[str, Any], result_key: str) -> Any:
    return (oracle.get("expectations") or {}).get(result_key)


def _designation_oracle_for_case(case: dict[str, Any]) -> dict[str, Any]:
    """Return the explicit, doctrine-independent designation capability oracle."""
    explicit_root = case.get("oracle") or {}
    explicit = explicit_root.get("designation") if isinstance(explicit_root, dict) else None
    if not isinstance(explicit, dict):
        return {
            "source": "none",
            "status": "unscored",
            "expectations": {},
            "open_policy_fields": [],
            "policy_options": {},
            "scored": False,
        }
    status = str(explicit.get("status") or "verified")
    open_policy_fields = sorted(
        set(str(value) for value in explicit.get("open_policy_fields") or [])
    )
    expectations = {
        field: explicit[field]
        for field in DESIGNATION_ORACLE_FIELDS
        if field in explicit and field not in open_policy_fields
    }
    if status in {"open", "unscored"}:
        expectations = {}
    return {
        "source": "explicit",
        "status": status,
        "expectations": expectations,
        "open_policy_fields": open_policy_fields,
        "policy_options": dict(explicit.get("policy_options") or {}),
        "scored": bool(expectations),
    }


def evaluate_designation_case(
    case: dict[str, Any], *, doctrine: str | None = None
) -> dict[str, Any]:
    """Test the designation capabilities required by one evidence case."""
    doctrine_name = str(doctrine or "proposed_changes")
    oracle = _designation_oracle_for_case(case)
    capabilities = {
        result_field: bool(_rule(doctrine_name, rule_key))
        for result_field, rule_key in DESIGNATION_ORACLE_FIELDS.items()
    }
    checks = [
        {
            "field": field,
            "expected": expected,
            "actual": capabilities[field],
            "passed": capabilities[field] == expected,
        }
        for field, expected in (oracle.get("expectations") or {}).items()
    ]
    failed = [check for check in checks if not check["passed"]]
    signal = "oracle_failure" if failed else "pass"
    if not oracle["scored"]:
        signal = "unscored"
    return {
        "case": case.get("case"),
        "id": case.get("id") or case.get("loc_id") or case.get("candidate_id"),
        "source_system": case.get("source_system"),
        "doctrine": doctrine_name,
        "designation": case.get("designation"),
        "capabilities": capabilities,
        "oracle": oracle,
        "oracle_checks": checks,
        "oracle_assertions": len(checks),
        "oracle_assertions_passed": sum(check["passed"] for check in checks),
        "failed_capabilities": [check["field"] for check in failed],
        "ok": not failed,
        "gate_ok": not failed,
        "signal": signal,
    }


def evaluate_designation_cases(
    cases: list[dict[str, Any]], *, doctrine: str | None = None
) -> list[dict[str, Any]]:
    return [
        evaluate_designation_case(case, doctrine=doctrine)
        for case in cases
        if _designation_oracle_for_case(case)["source"] == "explicit"
    ]


def _stewardship_oracle_for_case(case: dict[str, Any]) -> dict[str, Any]:
    """Return the explicit, doctrine-independent public-contract oracle."""
    explicit_root = case.get("oracle") or {}
    explicit = explicit_root.get("stewardship") if isinstance(explicit_root, dict) else None
    if not isinstance(explicit, dict):
        return {
            "source": "none",
            "status": "unscored",
            "expectations": {},
            "open_policy_fields": [],
            "policy_options": {},
            "scored": False,
        }
    status = str(explicit.get("status") or "verified")
    open_policy_fields = sorted(
        set(str(value) for value in explicit.get("open_policy_fields") or [])
    )
    expectations = {
        field: explicit[field]
        for field in STEWARDSHIP_ORACLE_FIELDS
        if field in explicit and field not in open_policy_fields
    }
    if status in {"open", "unscored"}:
        expectations = {}
    return {
        "source": "explicit",
        "status": status,
        "expectations": expectations,
        "open_policy_fields": open_policy_fields,
        "policy_options": dict(explicit.get("policy_options") or {}),
        "scored": bool(expectations),
    }


def evaluate_stewardship_case(
    case: dict[str, Any],
    *,
    doctrine: str | None = None,
    rule_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Test stewardship and reproducibility capabilities against one evidence case."""
    doctrine_name = str(doctrine or "proposed_changes")
    oracle = _stewardship_oracle_for_case(case)
    overrides = rule_overrides or {}
    capabilities = {
        result_field: bool(
            overrides[rule_key]
            if rule_key in overrides
            else _rule(doctrine_name, rule_key)
        )
        for result_field, rule_key in STEWARDSHIP_ORACLE_FIELDS.items()
    }
    checks = [
        {
            "field": field,
            "expected": expected,
            "actual": capabilities[field],
            "passed": capabilities[field] == expected,
        }
        for field, expected in (oracle.get("expectations") or {}).items()
    ]
    failed = [check for check in checks if not check["passed"]]
    signal = "oracle_failure" if failed else "pass"
    if not oracle["scored"]:
        signal = "unscored"
    return {
        "case": case.get("case"),
        "id": case.get("id") or case.get("loc_id") or case.get("candidate_id"),
        "source_system": case.get("source_system"),
        "doctrine": doctrine_name,
        "stewardship": case.get("stewardship"),
        "capabilities": capabilities,
        "oracle": oracle,
        "oracle_checks": checks,
        "oracle_assertions": len(checks),
        "oracle_assertions_passed": sum(check["passed"] for check in checks),
        "failed_capabilities": [check["field"] for check in failed],
        "ok": not failed,
        "gate_ok": not failed,
        "signal": signal,
    }


def evaluate_stewardship_cases(
    cases: list[dict[str, Any]],
    *,
    doctrine: str | None = None,
    rule_overrides: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    return [
        evaluate_stewardship_case(
            case,
            doctrine=doctrine,
            rule_overrides=rule_overrides,
        )
        for case in cases
        if _stewardship_oracle_for_case(case)["source"] == "explicit"
    ]


def stewardship_ablation_report(
    cases: list[dict[str, Any]], *, doctrine: str = "stewarded_release_graph"
) -> dict[str, Any]:
    """Disable each stewardship rule independently and measure lost assertions."""
    manifest = doctrine_manifest(doctrine)
    baseline_results = evaluate_stewardship_cases(cases, doctrine=doctrine)
    baseline_assertions = sum(result["oracle_assertions"] for result in baseline_results)
    baseline_passed = sum(
        result["oracle_assertions_passed"] for result in baseline_results
    )
    mutations: list[dict[str, Any]] = []
    for capability, rule_key in STEWARDSHIP_ORACLE_FIELDS.items():
        baseline_value = bool(manifest["rules"][rule_key])
        mutated_results = evaluate_stewardship_cases(
            cases,
            doctrine=doctrine,
            rule_overrides={rule_key: not baseline_value},
        )
        mutated_passed = sum(
            result["oracle_assertions_passed"] for result in mutated_results
        )
        failed_cases = [
            {
                "case": result["case"],
                "id": result["id"],
                "failed_capabilities": result["failed_capabilities"],
            }
            for result in mutated_results
            if not result["gate_ok"]
        ]
        mutations.append(
            {
                "capability": capability,
                "rule": rule_key,
                "baseline_value": baseline_value,
                "mutated_value": not baseline_value,
                "oracle_assertions": baseline_assertions,
                "oracle_assertions_passed": mutated_passed,
                "assertion_loss": baseline_passed - mutated_passed,
                "failure_case_count": len(failed_cases),
                "failure_cases": failed_cases,
            }
        )
    case_concentration = Counter(
        failure["case"]
        for mutation in mutations
        for failure in mutation["failure_cases"]
    )
    return {
        "doctrine": doctrine,
        "doctrine_fingerprint": manifest["fingerprint"],
        "oracle_fingerprint": oracle_fingerprint(cases),
        "baseline": {
            "case_count": len(baseline_results),
            "oracle_assertions": baseline_assertions,
            "oracle_assertions_passed": baseline_passed,
            "gate_ok": all(result["gate_ok"] for result in baseline_results),
        },
        "mutations": mutations,
        "all_rules_have_observed_contribution": all(
            mutation["assertion_loss"] > 0 for mutation in mutations
        ),
        "capabilities_below_two_supporting_cases": [
            mutation["capability"]
            for mutation in mutations
            if mutation["failure_case_count"] < 2
        ],
        "case_concentration": dict(
            sorted(case_concentration.items(), key=lambda item: (-item[1], item[0]))
        ),
    }


def evaluate_identity_case(
    case: dict[str, Any],
    *,
    doctrine: str | None = None,
    mode: str = "declared",
) -> dict[str, Any]:
    """Evaluate one weird-geography fixture against the loc_id doctrine.

    This is intentionally deterministic and schema-light. It is a guardrail for
    design fixtures, not a full geometry resolver.
    """
    if mode not in {"declared", "raw"}:
        raise ValueError(f"unknown evaluation mode {mode!r}")
    identifier = case.get("id") or case.get("loc_id") or case.get("candidate_id")
    record = case if mode == "declared" else {}
    family_id = record.get("family_id")
    oracle = _oracle_for_case(case, mode=mode)
    role = infer_identity_role(identifier, family_id=family_id, doctrine=doctrine)
    loc_family = classify_loc_id_family(identifier)
    first_segment_scope = infer_first_segment_scope(identifier, family_id=family_id, doctrine=doctrine)
    may_encode_admin = loc_id_may_encode_admin_hierarchy(identifier, family_id=family_id, doctrine=doctrine)
    parent_semantics = expected_parent_semantics(identifier, family_id=family_id, doctrine=doctrine)
    registry = lookup_namespace(identifier, doctrine=doctrine)
    reference_level = record.get("reference_level") or infer_admin_reference_level(identifier, family_id=family_id, doctrine=doctrine)
    reference_level_reason = record.get("reference_level_reason")
    placement_semantics = expected_placement_semantics(identifier, family_id=family_id, doctrine=doctrine)
    issues: list[str] = []

    expected_role = _expected_value(oracle, "role")
    if expected_role and expected_role not in IDENTITY_ROLES:
        issues.append(f"unknown expected_role {expected_role!r}")
    elif expected_role and role != expected_role:
        issues.append(f"role mismatch: expected {expected_role}, got {role}")

    expected_scope = _expected_value(oracle, "first_segment_scope")
    if expected_scope and first_segment_scope != expected_scope:
        issues.append(f"first segment scope mismatch: expected {expected_scope}, got {first_segment_scope}")

    expected_parent = _expected_value(oracle, "parent_semantics")
    if expected_parent and parent_semantics != expected_parent:
        issues.append(f"parent semantics mismatch: expected {expected_parent}, got {parent_semantics}")

    expected_reference_level = _expected_value(oracle, "reference_level")
    if expected_reference_level and reference_level != expected_reference_level:
        issues.append(f"reference level mismatch: expected {expected_reference_level}, got {reference_level}")

    expected_placement = _expected_value(oracle, "placement_semantics")
    if expected_placement and placement_semantics != expected_placement:
        issues.append(f"placement semantics mismatch: expected {expected_placement}, got {placement_semantics}")

    public_promise = record.get("public_promise")
    if public_promise and public_promise not in PUBLIC_PROMISES:
        issues.append(f"unknown public_promise {public_promise!r}")

    if role != "loc_id" and record.get("should_persist_as_loc_id"):
        issues.append(f"{role} must not be persisted as loc_id")

    if role == "loc_id" and not family_id and not loc_family and not registry:
        issues.append("loc_id case needs a family_id or recognized runtime family")

    if not may_encode_admin and record.get("admin_level") is not None:
        issues.append("non-admin families must not expose admin_level as spine depth")

    if reference_level and reference_level not in REFERENCE_LEVELS:
        issues.append(f"unknown reference_level {reference_level!r}")

    if reference_level_reason and reference_level_reason not in REFERENCE_LEVEL_REASONS:
        issues.append(f"unknown reference_level_reason {reference_level_reason!r}")

    if may_encode_admin and reference_level_reason and reference_level_reason not in {"admin_spine", "official_admin_equivalent", "temporal_spine_version"}:
        issues.append("admin families need an admin reference_level_reason")

    if not may_encode_admin and reference_level and not reference_level_reason:
        issues.append("non-admin reference_level requires reference_level_reason")

    if not may_encode_admin and reference_level_reason == "admin_spine":
        issues.append("non-admin reference_level must not claim admin_spine")

    if parent_semantics != "strict_admin_parent" and record.get("parent_id"):
        issues.append("non-admin parent_id must be represented as context or bridge metadata")

    containing_loc_id = record.get("containing_loc_id")
    containment_method = record.get("containment_method")
    crosses_admin_boundaries = record.get("crosses_admin_boundaries")
    if containing_loc_id and _rule(doctrine, "placement_policy") != "containing_loc_id":
        issues.append("containing_loc_id belongs to containing_loc_id doctrine or resolver placement output")

    if containing_loc_id and not containment_method:
        issues.append("containing_loc_id requires containment_method")

    if containment_method and containment_method not in CONTAINMENT_METHODS:
        issues.append(f"unknown containment_method {containment_method!r}")

    if crosses_admin_boundaries is True and containment_method == "full_geometry":
        issues.append("cross-boundary geography cannot use full_geometry containment_method")

    if crosses_admin_boundaries is True and containing_loc_id and not record.get("overlapping_admin_loc_ids"):
        issues.append("cross-boundary containing_loc_id requires overlapping_admin_loc_ids")

    parent_status = record.get("parent_status")
    if parent_status == "contested" and not record.get("parent_claims"):
        issues.append("contested parentage requires parent_claims")
    if parent_status in {"missing", "unverified"}:
        parent_token = _clean(record.get("parent_id"))
        if parent_token and "NULL" not in parent_token:
            issues.append("missing or unverified admin parent must use NULL<n> sentinel")

    temporal_rule = record.get("temporal_rule")
    if temporal_rule == "supersession_required" and not (
        record.get("superseded_by") or record.get("supersedes")
    ):
        issues.append("supersession_required needs superseded_by or supersedes")

    if record.get("bridge_required") and not record.get("required_bridge_type"):
        issues.append("bridge_required cases must declare required_bridge_type")

    findings = [{"code": _issue_code(issue), "message": issue} for issue in issues]
    known_messages = set(oracle.get("known_issue_messages") or [])
    known_codes = set(oracle.get("known_issue_codes") or [])
    known_findings = [
        finding
        for finding in findings
        if finding["message"] in known_messages or finding["code"] in known_codes
    ]
    unexpected_findings = [finding for finding in findings if finding not in known_findings]
    actual_messages = {finding["message"] for finding in findings}
    actual_codes = {finding["code"] for finding in findings}
    resolved_known_issues = sorted(known_messages - actual_messages)
    resolved_known_issue_codes = sorted(known_codes - actual_codes)
    oracle_checks = [
        {
            "field": result_key,
            "expected": expected,
            "actual": {
                "role": role,
                "first_segment_scope": first_segment_scope,
                "parent_semantics": parent_semantics,
                "reference_level": reference_level,
                "placement_semantics": placement_semantics,
            }[result_key],
            "passed": expected
            == {
                "role": role,
                "first_segment_scope": first_segment_scope,
                "parent_semantics": parent_semantics,
                "reference_level": reference_level,
                "placement_semantics": placement_semantics,
            }[result_key],
        }
        for result_key, expected in (oracle.get("expectations") or {}).items()
    ]
    signal = "pass"
    if unexpected_findings:
        signal = "unexpected_issue"
    elif known_findings:
        signal = "known_issue"
    elif not oracle.get("scored"):
        signal = "unscored"

    return {
        "case": case.get("case"),
        "id": identifier,
        "source_system": case.get("source_system"),
        "sample_kind": case.get("sample_kind"),
        "doctrine": doctrine or "proposed_changes",
        "mode": mode,
        "namespace": (lookup_namespace(identifier, doctrine=doctrine) or {}).get("namespace"),
        "role": role,
        "loc_id_family": loc_family,
        "first_segment_scope": first_segment_scope,
        "may_encode_admin_hierarchy": may_encode_admin,
        "parent_semantics": parent_semantics,
        "reference_level": reference_level,
        "reference_level_reason": reference_level_reason,
        "placement_semantics": placement_semantics,
        "findings": findings,
        "issues": issues,
        "known_findings": known_findings,
        "unexpected_findings": unexpected_findings,
        "resolved_known_issues": resolved_known_issues,
        "resolved_known_issue_codes": resolved_known_issue_codes,
        "expected_issues": oracle.get("known_issue_messages") or [],
        "unexpected_issues": [finding["message"] for finding in unexpected_findings],
        "missing_expected_issues": resolved_known_issues,
        "oracle": oracle,
        "oracle_checks": oracle_checks,
        "oracle_assertions": len(oracle_checks),
        "oracle_assertions_passed": sum(check["passed"] for check in oracle_checks),
        "legacy_doctrine_expectations_ignored": sorted(
            key for key in case if key.endswith("_by_doctrine")
        ),
        "design_questions": case.get("design_questions") or [],
        "clean": not findings,
        "ok": not unexpected_findings,
        "gate_ok": not unexpected_findings,
        "signal": signal,
    }


def evaluate_identity_cases(cases: list[dict[str, Any]], *, doctrine: str | None = None) -> list[dict[str, Any]]:
    return [evaluate_identity_case(case, doctrine=doctrine) for case in cases]


def evaluate_dual_mode_case(case: dict[str, Any], *, doctrine: str | None = None) -> dict[str, Any]:
    """Compare declared-metadata classification with raw-string classification."""
    declared = evaluate_identity_case(case, doctrine=doctrine, mode="declared")
    raw = evaluate_identity_case(case, doctrine=doctrine, mode="raw")
    deltas: list[str] = []
    for key in (
        "role",
        "first_segment_scope",
        "parent_semantics",
        "may_encode_admin_hierarchy",
        "reference_level",
        "placement_semantics",
    ):
        if declared.get(key) != raw.get(key):
            deltas.append(f"{key}: declared={declared.get(key)} raw={raw.get(key)}")

    signal = "pass"
    if deltas:
        signal = "raw_declared_delta"
    if not declared.get("gate_ok") or not raw.get("gate_ok"):
        signal = "oracle_failure"
    if deltas and case.get("allow_doctrine_conflict"):
        signal = "doctrine_conflict"

    return {
        "case": case.get("case"),
        "id": case.get("id") or case.get("loc_id") or case.get("candidate_id"),
        "source_system": case.get("source_system"),
        "declared": declared,
        "raw": raw,
        "deltas": deltas,
        "ok": bool(declared.get("gate_ok")) and bool(raw.get("gate_ok")),
        "gate_ok": bool(declared.get("gate_ok")) and bool(raw.get("gate_ok")),
        "signal": signal,
    }


def evaluate_dual_mode_cases(cases: list[dict[str, Any]], *, doctrine: str | None = None) -> list[dict[str, Any]]:
    return [evaluate_dual_mode_case(case, doctrine=doctrine) for case in cases]


def compare_doctrine_case(case: dict[str, Any], *, left: str = "present_system", right: str = "proposed_changes") -> dict[str, Any]:
    left_result = evaluate_dual_mode_case(case, doctrine=left)
    right_result = evaluate_dual_mode_case(case, doctrine=right)
    left_designation = evaluate_designation_case(case, doctrine=left)
    right_designation = evaluate_designation_case(case, doctrine=right)
    left_stewardship = evaluate_stewardship_case(case, doctrine=left)
    right_stewardship = evaluate_stewardship_case(case, doctrine=right)
    deltas: list[str] = []
    for mode in ("declared", "raw"):
        for key in (
            "role",
            "first_segment_scope",
            "parent_semantics",
            "may_encode_admin_hierarchy",
            "reference_level",
            "placement_semantics",
            "namespace",
        ):
            if left_result[mode].get(key) != right_result[mode].get(key):
                deltas.append(
                    f"{mode}.{key}: {left}={left_result[mode].get(key)} {right}={right_result[mode].get(key)}"
                )
    if left_designation["oracle"]["source"] == "explicit":
        for key in DESIGNATION_ORACLE_FIELDS:
            if left_designation["capabilities"][key] != right_designation["capabilities"][key]:
                deltas.append(
                    f"designation.{key}: {left}={left_designation['capabilities'][key]} "
                    f"{right}={right_designation['capabilities'][key]}"
                )
    if left_stewardship["oracle"]["source"] == "explicit":
        for key in STEWARDSHIP_ORACLE_FIELDS:
            if left_stewardship["capabilities"][key] != right_stewardship["capabilities"][key]:
                deltas.append(
                    f"stewardship.{key}: {left}={left_stewardship['capabilities'][key]} "
                    f"{right}={right_stewardship['capabilities'][key]}"
                )
    signal = "pass" if not deltas else "doctrine_delta"
    designation_scored = left_designation["oracle"]["source"] == "explicit"
    stewardship_scored = left_stewardship["oracle"]["source"] == "explicit"
    if (
        not right_result.get("gate_ok")
        or not left_result.get("gate_ok")
        or (designation_scored and not left_designation.get("gate_ok"))
        or (designation_scored and not right_designation.get("gate_ok"))
        or (stewardship_scored and not left_stewardship.get("gate_ok"))
        or (stewardship_scored and not right_stewardship.get("gate_ok"))
    ):
        signal = "oracle_failure"
    return {
        "case": case.get("case"),
        "id": case.get("id") or case.get("loc_id") or case.get("candidate_id"),
        "source_system": case.get("source_system"),
        "left_doctrine": left,
        "right_doctrine": right,
        "left": left_result,
        "right": right_result,
        "left_designation": left_designation,
        "right_designation": right_designation,
        "left_stewardship": left_stewardship,
        "right_stewardship": right_stewardship,
        "deltas": deltas,
        "ok": bool(left_result.get("gate_ok"))
        and bool(right_result.get("gate_ok"))
        and (not designation_scored or bool(left_designation.get("gate_ok")))
        and (not designation_scored or bool(right_designation.get("gate_ok")))
        and (not stewardship_scored or bool(left_stewardship.get("gate_ok")))
        and (not stewardship_scored or bool(right_stewardship.get("gate_ok"))),
        "gate_ok": bool(left_result.get("gate_ok"))
        and bool(right_result.get("gate_ok"))
        and (not designation_scored or bool(left_designation.get("gate_ok")))
        and (not designation_scored or bool(right_designation.get("gate_ok")))
        and (not stewardship_scored or bool(left_stewardship.get("gate_ok")))
        and (not stewardship_scored or bool(right_stewardship.get("gate_ok"))),
        "signal": signal,
    }


def compare_doctrine_cases(
    cases: list[dict[str, Any]],
    *,
    left: str = "present_system",
    right: str = "proposed_changes",
) -> list[dict[str, Any]]:
    return [compare_doctrine_case(case, left=left, right=right) for case in cases]


def doctrine_manifest(doctrine: str | None = None) -> dict[str, Any]:
    """Return every executable assumption for a doctrine in reportable form."""
    doctrine_name = str(doctrine or "proposed_changes")
    profile = _profile(doctrine_name)
    rules = dict(profile.get("rules") or {})
    missing = [key for key in DOCTRINE_RULE_KEYS if key not in rules]
    if missing:
        raise ValueError(f"doctrine {doctrine_name} is missing explicit rules: {', '.join(missing)}")
    undeclared = sorted(set(rules) - set(DOCTRINE_RULE_KEYS))
    if undeclared:
        raise ValueError(f"doctrine {doctrine_name} has undeclared rules: {', '.join(undeclared)}")
    registry = []
    seen_namespaces: set[str] = set()
    for order, entry in enumerate(profile.get("registry") or [], start=1):
        namespace = str(entry["namespace"])
        if namespace in seen_namespaces:
            raise ValueError(f"doctrine {doctrine_name} repeats namespace {namespace!r}")
        seen_namespaces.add(namespace)
        try:
            re.compile(str(entry["pattern"]))
        except re.error as exc:
            raise ValueError(f"doctrine {doctrine_name} has invalid pattern for {namespace}: {exc}") from exc
        registry.append(
            {
                "rule_id": f"namespace:{namespace}",
                "order": order,
                "is_admin_fallback": namespace == "current_admin_local",
                **entry,
            }
        )
    fallback_count = sum(bool(entry["is_admin_fallback"]) for entry in registry)
    if fallback_count != 1:
        raise ValueError(f"doctrine {doctrine_name} must declare exactly one admin fallback")
    patterns = [str(entry.get("pattern") or "") for entry in registry]
    fingerprint = _stable_fingerprint({"rules": rules, "registry": registry})
    return {
        "doctrine": doctrine_name,
        "fingerprint": fingerprint,
        "description": profile.get("description"),
        "harness_contract": dict(WIND_TUNNEL_CONTRACT),
        "rules": rules,
        "registry": registry,
        "decisions": doctrine_decisions(doctrine_name),
        "complexity": {
            "policy_rule_count": len(rules),
            "nonbaseline_policy_rule_count": sum(
                rules[key] != BASE_DOCTRINE_RULES[key] for key in DOCTRINE_RULE_KEYS
            ),
            "enabled_designation_capability_count": sum(
                bool(rules[rule_key]) for rule_key in DESIGNATION_ORACLE_FIELDS.values()
            ),
            "enabled_stewardship_capability_count": sum(
                bool(rules[rule_key]) for rule_key in STEWARDSHIP_ORACLE_FIELDS.values()
            ),
            "namespace_rule_count": len(registry),
            "regex_alternative_terms_estimate": sum(pattern.count("|") + 1 for pattern in patterns),
            "pattern_characters": sum(len(pattern) for pattern in patterns),
            "precedence_exceptions": int(rules["admin_fallback_precedence"] == "last"),
        },
    }


def compare_doctrine_rules(left: str, right: str) -> list[dict[str, Any]]:
    """Return policy and namespace differences before comparing case outputs."""
    left_manifest = doctrine_manifest(left)
    right_manifest = doctrine_manifest(right)
    differences: list[dict[str, Any]] = []
    for key in DOCTRINE_RULE_KEYS:
        left_value = left_manifest["rules"].get(key)
        right_value = right_manifest["rules"].get(key)
        if left_value != right_value:
            differences.append(
                {"kind": "policy", "rule": key, "left": left_value, "right": right_value}
            )

    left_registry = {entry["namespace"]: entry for entry in left_manifest["registry"]}
    right_registry = {entry["namespace"]: entry for entry in right_manifest["registry"]}
    for namespace in sorted(set(left_registry) | set(right_registry)):
        left_entry = left_registry.get(namespace)
        right_entry = right_registry.get(namespace)
        if left_entry is None or right_entry is None:
            differences.append(
                {
                    "kind": "namespace",
                    "rule": namespace,
                    "left": "absent" if left_entry is None else "present",
                    "right": "absent" if right_entry is None else "present",
                }
            )
            continue
        ignored_fields = {"rule_id", "namespace", "is_admin_fallback"}
        for field in sorted((set(left_entry) | set(right_entry)) - ignored_fields):
            left_value = left_entry.get(field)
            right_value = right_entry.get(field)
            if left_value != right_value:
                differences.append(
                    {
                        "kind": "namespace",
                        "rule": f"{namespace}.{field}",
                        "left": left_value,
                        "right": right_value,
                    }
                )
    return differences


def registry_audit(cases: list[dict[str, Any]], *, doctrine: str | None = None) -> dict[str, Any]:
    """Measure recognition, overlaps, precedence, and unused namespace rules."""
    doctrine_name = str(doctrine or "proposed_changes")
    registry = _profile(doctrine_name)["registry"]
    selected_counts: Counter[str] = Counter()
    matched_counts: Counter[str] = Counter()
    overlaps: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    for case in cases:
        identifier = case.get("id") or case.get("loc_id") or case.get("candidate_id")
        value = _clean(identifier)
        matches = [
            str(entry["namespace"])
            for entry in registry
            if re.fullmatch(str(entry["pattern"]), value)
        ]
        matched_counts.update(matches)
        selected = lookup_namespace(identifier, doctrine=doctrine_name)
        selected_namespace = str(selected["namespace"]) if selected else None
        if selected_namespace:
            selected_counts[selected_namespace] += 1
        else:
            unmatched.append({"case": case.get("case"), "id": identifier})
        if len(matches) > 1:
            specific_matches = [name for name in matches if name != "current_admin_local"]
            overlaps.append(
                {
                    "case": case.get("case"),
                    "id": identifier,
                    "matches": matches,
                    "specific_matches": specific_matches,
                    "has_specific_collision": len(specific_matches) > 1,
                    "selected": selected_namespace,
                }
            )
    namespaces = [str(entry["namespace"]) for entry in registry]
    return {
        "doctrine": doctrine_name,
        "case_count": len(cases),
        "recognized_cases": len(cases) - len(unmatched),
        "unmatched_cases": unmatched,
        "overlap_cases": overlaps,
        "overlap_count": len(overlaps),
        "specific_collision_count": sum(bool(item["has_specific_collision"]) for item in overlaps),
        "matched_rule_hits": dict(sorted(matched_counts.items())),
        "selected_rule_hits": dict(sorted(selected_counts.items())),
        "unexercised_namespace_rules": [name for name in namespaces if not matched_counts[name]],
        "shadowed_namespace_rules": [
            name for name in namespaces if matched_counts[name] and not selected_counts[name]
        ],
        "unused_namespace_rules": [name for name in namespaces if not selected_counts[name]],
    }


def oracle_fingerprint(cases: list[dict[str, Any]]) -> str:
    """Return a stable identity for the exact shared oracle contract."""
    payload = []
    for case in cases:
        payload.append(
            {
                "case": case.get("case"),
                "id": case.get("id") or case.get("loc_id") or case.get("candidate_id"),
                "declared": _oracle_for_case(case, mode="declared"),
                "raw": _oracle_for_case(case, mode="raw"),
                "designation": _designation_oracle_for_case(case),
                "stewardship": _stewardship_oracle_for_case(case),
            }
        )
    return _stable_fingerprint(payload)


def _valid_shaped_sibling_area_depth(metadata: Any) -> bool:
    """Validate the minimum reproducible evidence for area-derived sibling ancestry."""
    if not isinstance(metadata, dict):
        return False
    profile = metadata.get("area_profile")
    if not isinstance(profile, dict):
        return False
    prior_form = isinstance(profile.get("level_median_area_km2"), dict)
    medians = (
        profile.get("level_median_area_km2")
        if prior_form
        else profile.get("level_median_area_sq_km")
    )
    thresholds = (
        profile.get("depth_thresholds_km2")
        if prior_form
        else profile.get("enter_level_max_area_sq_km")
    )
    if not isinstance(medians, dict) or not isinstance(thresholds, dict):
        return False
    try:
        levels = sorted(medians, key=lambda value: int(str(value).split("_")[-1]))
        median_values = [float(medians[level]) for level in levels]
        owned_area = float(metadata.get("owned_area_km2"))
    except (TypeError, ValueError):
        return False
    if len(levels) < 2 or owned_area <= 0 or any(value <= 0 for value in median_values):
        return False
    if any(left <= right for left, right in zip(median_values, median_values[1:])):
        return False

    expected_level_number = int(str(levels[-1]).split("_")[-1])
    for shallow, deep, shallow_area, deep_area in zip(
        levels, levels[1:], median_values, median_values[1:]
    ):
        shallow_number = int(str(shallow).split("_")[-1])
        deep_number = int(str(deep).split("_")[-1])
        key = f"{shallow}_to_{deep}" if prior_form else str(deep_number)
        try:
            threshold = float(thresholds[key])
        except (KeyError, TypeError, ValueError):
            return False
        geometric_midpoint = (shallow_area * deep_area) ** 0.5
        if abs(threshold - geometric_midpoint) > max(1e-9, geometric_midpoint * 1e-9):
            return False
        if owned_area >= threshold:
            expected_level_number = shallow_number
            break
    expected_level = f"label_{expected_level_number}"

    owner_iso3 = str(metadata.get("country_owner_iso3") or "")
    canonical_loc_id = str(metadata.get("canonical_loc_id") or "")
    sibling_anchor = str(metadata.get("sibling_anchor_loc_id") or "")
    spine_fingerprint = str(
        metadata.get("spine_candidate_fingerprint")
        or metadata.get("stable_spine_fingerprint")
        or ""
    )
    profile_fingerprint = str(
        profile.get("spine_candidate_fingerprint")
        or profile.get("stable_spine_fingerprint")
        or ""
    )
    analysis_crs = metadata.get("equal_area_crs") or profile.get("analysis_crs")
    profile_contract_valid = (
        profile.get("threshold_method") == "geometric_midpoint_adjacent_medians"
        and bool(profile.get("derivation_version"))
        if prior_form
        else profile.get("area_unit") == "square_kilometre"
        and profile.get("depth_rule")
        == "deepest_level_whose_geometric_midpoint_threshold_contains_feature_area"
        and bool(profile.get("schema_version"))
        and bool(profile.get("builder_version"))
    )
    return bool(
        re.fullmatch(r"[A-Z]{3}", owner_iso3)
        and canonical_loc_id.startswith(f"{owner_iso3}-")
        and sibling_anchor.startswith(f"{owner_iso3}-")
        and canonical_loc_id.startswith(f"{sibling_anchor}-")
        and metadata.get("geometry_role") in {"official_polygon", "official_multipolygon"}
        and metadata.get("owned_extent_method") == "complete_owned_physical_area"
        and analysis_crs
        and metadata.get("selected_reference_level") == expected_level
        and metadata.get("anchor_method")
        == "dominant_owned_area_overlap_at_selected_depth"
        and metadata.get("population_affects_depth") is False
        and metadata.get("importance_affects_depth") is False
        and metadata.get("boundary_crossing_affects_depth") is False
        and metadata.get("other_intersections_retained_as_bridges") is True
        and metadata.get("affects_identity") is True
        and re.fullmatch(r"[0-9a-f]{64}", spine_fingerprint)
        and profile_fingerprint == spine_fingerprint
        and profile_contract_valid
    )


def corpus_audit(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Expose fixture provenance, oracle coverage, and legacy hidden assumptions."""
    case_counts = Counter(str(case.get("case") or "") for case in cases)
    id_counts = Counter(
        str(case.get("id") or case.get("loc_id") or case.get("candidate_id") or "")
        for case in cases
    )
    missing_case_names = [index for index, case in enumerate(cases) if not case.get("case")]
    missing_identifiers = [
        index
        for index, case in enumerate(cases)
        if not (case.get("id") or case.get("loc_id") or case.get("candidate_id"))
    ]
    doctrine_override_cases = []
    explicit_declared = 0
    explicit_raw = 0
    explicit_designation = 0
    explicit_stewardship = 0
    declared_scored = 0
    raw_scored = 0
    designation_scored = 0
    stewardship_scored = 0
    legacy_expectation_cases = []
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    allowed_explicit_fields = {
        "status",
        "known_issues",
        "known_issue_codes",
        "open_policy_fields",
        "policy_options",
        *ORACLE_FIELDS.keys(),
        *ORACLE_FIELDS.values(),
    }
    allowed_designation_fields = {
        "status",
        "open_policy_fields",
        "policy_options",
        *DESIGNATION_ORACLE_FIELDS,
    }
    allowed_stewardship_fields = {
        "status",
        "open_policy_fields",
        "policy_options",
        *STEWARDSHIP_ORACLE_FIELDS,
    }
    for index, case in enumerate(cases):
        explicit = case.get("oracle") or {}
        if "oracle" in case and not isinstance(case.get("oracle"), dict):
            errors.append({"code": "INVALID_ORACLE_ROOT", "index": index, "case": case.get("case")})
            explicit = {}
        if isinstance(explicit, dict):
            unknown_modes = sorted(
                set(explicit) - {"declared", "raw", "designation", "stewardship"}
            )
            if unknown_modes:
                errors.append(
                    {
                        "code": "UNKNOWN_ORACLE_MODES",
                        "index": index,
                        "case": case.get("case"),
                        "modes": unknown_modes,
                    }
                )
        explicit_declared += int(isinstance(explicit, dict) and isinstance(explicit.get("declared"), dict))
        explicit_raw += int(isinstance(explicit, dict) and isinstance(explicit.get("raw"), dict))
        explicit_designation += int(
            isinstance(explicit, dict) and isinstance(explicit.get("designation"), dict)
        )
        explicit_stewardship += int(
            isinstance(explicit, dict) and isinstance(explicit.get("stewardship"), dict)
        )
        declared_scored += int(_oracle_for_case(case, mode="declared")["scored"])
        raw_scored += int(_oracle_for_case(case, mode="raw")["scored"])
        designation_scored += int(_designation_oracle_for_case(case)["scored"])
        stewardship_scored += int(_stewardship_oracle_for_case(case)["scored"])
        override_keys = sorted(key for key in case if key.endswith("_by_doctrine"))
        if override_keys:
            doctrine_override_cases.append(
                {"case": case.get("case"), "id": case.get("id"), "fields": override_keys}
            )
        legacy_keys = sorted(
            key
            for key in case
            if key in {*ORACLE_FIELDS.values(), "expected_issues", "expected_issue_codes"}
        )
        if legacy_keys:
            legacy_expectation_cases.append(
                {"case": case.get("case"), "id": case.get("id"), "fields": legacy_keys}
            )
        if isinstance(explicit, dict):
            for mode in ("declared", "raw"):
                mode_oracle = explicit.get(mode)
                if mode_oracle is None:
                    continue
                if not isinstance(mode_oracle, dict):
                    errors.append(
                        {"code": "INVALID_ORACLE_MODE", "index": index, "case": case.get("case"), "mode": mode}
                    )
                    continue
                unknown_fields = sorted(set(mode_oracle) - allowed_explicit_fields)
                if unknown_fields:
                    errors.append(
                        {
                            "code": "UNKNOWN_ORACLE_FIELDS",
                            "index": index,
                            "case": case.get("case"),
                            "mode": mode,
                            "fields": unknown_fields,
                        }
                    )
                status = str(mode_oracle.get("status") or "verified")
                if status not in ORACLE_STATUSES:
                    errors.append(
                        {
                            "code": "INVALID_ORACLE_STATUS",
                            "index": index,
                            "case": case.get("case"),
                            "mode": mode,
                            "value": status,
                        }
                    )
                open_fields = [str(value) for value in mode_oracle.get("open_policy_fields") or []]
                invalid_open = sorted(set(open_fields) - set(ORACLE_FIELDS))
                if invalid_open:
                    errors.append(
                        {
                            "code": "INVALID_OPEN_POLICY_FIELDS",
                            "index": index,
                            "case": case.get("case"),
                            "mode": mode,
                            "fields": invalid_open,
                        }
                    )
                asserted_open = sorted(
                    field
                    for field in open_fields
                    if field in mode_oracle or ORACLE_FIELDS.get(field) in mode_oracle
                )
                if asserted_open:
                    errors.append(
                        {
                            "code": "OPEN_POLICY_FIELD_ASSERTED",
                            "index": index,
                            "case": case.get("case"),
                            "mode": mode,
                            "fields": asserted_open,
                        }
                    )
                role = mode_oracle.get("role", mode_oracle.get("expected_role"))
                if role is not None and role not in IDENTITY_ROLES:
                    errors.append(
                        {
                            "code": "INVALID_ORACLE_ROLE",
                            "index": index,
                            "case": case.get("case"),
                            "mode": mode,
                            "value": role,
                        }
                    )
            designation_oracle = explicit.get("designation")
            if designation_oracle is not None:
                if not isinstance(designation_oracle, dict):
                    errors.append(
                        {
                            "code": "INVALID_DESIGNATION_ORACLE",
                            "index": index,
                            "case": case.get("case"),
                        }
                    )
                else:
                    unknown_fields = sorted(
                        set(designation_oracle) - allowed_designation_fields
                    )
                    if unknown_fields:
                        errors.append(
                            {
                                "code": "UNKNOWN_DESIGNATION_ORACLE_FIELDS",
                                "index": index,
                                "case": case.get("case"),
                                "fields": unknown_fields,
                            }
                        )
                    status = str(designation_oracle.get("status") or "verified")
                    if status not in ORACLE_STATUSES:
                        errors.append(
                            {
                                "code": "INVALID_DESIGNATION_ORACLE_STATUS",
                                "index": index,
                                "case": case.get("case"),
                                "value": status,
                            }
                        )
                    open_fields = [
                        str(value)
                        for value in designation_oracle.get("open_policy_fields") or []
                    ]
                    invalid_open = sorted(
                        set(open_fields) - set(DESIGNATION_ORACLE_FIELDS)
                    )
                    if invalid_open:
                        errors.append(
                            {
                                "code": "INVALID_DESIGNATION_OPEN_POLICY_FIELDS",
                                "index": index,
                                "case": case.get("case"),
                                "fields": invalid_open,
                            }
                        )
                    asserted_open = sorted(
                        field for field in open_fields if field in designation_oracle
                    )
                    if asserted_open:
                        errors.append(
                            {
                                "code": "DESIGNATION_OPEN_POLICY_FIELD_ASSERTED",
                                "index": index,
                                "case": case.get("case"),
                                "fields": asserted_open,
                            }
                        )
                    non_boolean = sorted(
                        field
                        for field in DESIGNATION_ORACLE_FIELDS
                        if field in designation_oracle
                        and not isinstance(designation_oracle[field], bool)
                    )
                    if non_boolean:
                        errors.append(
                            {
                                "code": "INVALID_DESIGNATION_CAPABILITY_VALUE",
                                "index": index,
                                "case": case.get("case"),
                                "fields": non_boolean,
                            }
                        )
                    if not isinstance(case.get("designation"), dict):
                        errors.append(
                            {
                                "code": "MISSING_DESIGNATION_METADATA",
                                "index": index,
                                "case": case.get("case"),
                            }
                        )
                    else:
                        metadata = case["designation"]
                        required_metadata: dict[str, bool] = {
                            "represents_membership_set": case.get("family_id")
                            in {"membership_set", "designation_set"},
                            "preserves_member_family": bool(metadata.get("member_families")),
                            "preserves_compound_subject": "population_within_geography"
                            in (metadata.get("member_target_kinds") or []),
                            "preserves_independent_clocks": bool(
                                metadata.get("base_geography_vintage")
                                and (metadata.get("valid_from") or metadata.get("valid_to"))
                            ),
                            "preserves_dependency_binding": bool(
                                metadata.get("dependencies")
                                and all(
                                    isinstance(dependency, dict)
                                    and dependency.get("membership_set_id")
                                    and dependency.get("binding_policy")
                                    for dependency in metadata.get("dependencies") or []
                                )
                            ),
                            "preserves_set_lifecycle": bool(metadata.get("status"))
                            and (
                                metadata.get("status") != "retired"
                                or "superseded_by" in metadata
                            ),
                            "preserves_member_attributes": bool(metadata.get("member_attributes")),
                            "treats_union_as_derived": metadata.get("geometry_truth")
                            == "members_primary_union_derived",
                            "preserves_authority_snapshot": bool(
                                metadata.get("authority") and metadata.get("authority_snapshot")
                            ),
                        }
                        missing_evidence = sorted(
                            field
                            for field, supported in required_metadata.items()
                            if designation_oracle.get(field) is True and not supported
                        )
                        if missing_evidence:
                            errors.append(
                                {
                                    "code": "MISSING_DESIGNATION_EVIDENCE",
                                    "index": index,
                                    "case": case.get("case"),
                                    "fields": missing_evidence,
                                }
                            )
            stewardship_oracle = explicit.get("stewardship")
            if stewardship_oracle is not None:
                if not isinstance(stewardship_oracle, dict):
                    errors.append(
                        {
                            "code": "INVALID_STEWARDSHIP_ORACLE",
                            "index": index,
                            "case": case.get("case"),
                        }
                    )
                else:
                    unknown_fields = sorted(
                        set(stewardship_oracle) - allowed_stewardship_fields
                    )
                    if unknown_fields:
                        errors.append(
                            {
                                "code": "UNKNOWN_STEWARDSHIP_ORACLE_FIELDS",
                                "index": index,
                                "case": case.get("case"),
                                "fields": unknown_fields,
                            }
                        )
                    status = str(stewardship_oracle.get("status") or "verified")
                    if status not in ORACLE_STATUSES:
                        errors.append(
                            {
                                "code": "INVALID_STEWARDSHIP_ORACLE_STATUS",
                                "index": index,
                                "case": case.get("case"),
                                "value": status,
                            }
                        )
                    open_fields = [
                        str(value)
                        for value in stewardship_oracle.get("open_policy_fields") or []
                    ]
                    invalid_open = sorted(
                        set(open_fields) - set(STEWARDSHIP_ORACLE_FIELDS)
                    )
                    if invalid_open:
                        errors.append(
                            {
                                "code": "INVALID_STEWARDSHIP_OPEN_POLICY_FIELDS",
                                "index": index,
                                "case": case.get("case"),
                                "fields": invalid_open,
                            }
                        )
                    asserted_open = sorted(
                        field for field in open_fields if field in stewardship_oracle
                    )
                    if asserted_open:
                        errors.append(
                            {
                                "code": "STEWARDSHIP_OPEN_POLICY_FIELD_ASSERTED",
                                "index": index,
                                "case": case.get("case"),
                                "fields": asserted_open,
                            }
                        )
                    non_boolean = sorted(
                        field
                        for field in STEWARDSHIP_ORACLE_FIELDS
                        if field in stewardship_oracle
                        and not isinstance(stewardship_oracle[field], bool)
                    )
                    if non_boolean:
                        errors.append(
                            {
                                "code": "INVALID_STEWARDSHIP_CAPABILITY_VALUE",
                                "index": index,
                                "case": case.get("case"),
                                "fields": non_boolean,
                            }
                        )
                    if not isinstance(case.get("stewardship"), dict):
                        errors.append(
                            {
                                "code": "MISSING_STEWARDSHIP_METADATA",
                                "index": index,
                                "case": case.get("case"),
                            }
                        )
                    else:
                        metadata = case["stewardship"]
                        release = metadata.get("geography_release") or {}
                        edge_type = metadata.get("edge_type")
                        required_metadata: dict[str, bool] = {
                            "separates_authority_scope": bool(
                                metadata.get("authority") and metadata.get("geographic_scope")
                            ),
                            "enforces_family_admission": bool(
                                metadata.get("admission_status")
                                and metadata.get("identity_promise")
                                and metadata.get("lifecycle_policy")
                            ),
                            "separates_identity_publication": bool(
                                metadata.get("identity_promise")
                                and metadata.get("publication_posture")
                            ),
                            "preserves_public_resolution": metadata.get("resolution_policy")
                            == "tombstone_or_successor",
                            "supports_temporal_identifier_network": bool(
                                isinstance(metadata.get("identifier_assertions"), list)
                                and len(metadata["identifier_assertions"]) >= 2
                                and all(
                                    isinstance(assertion, dict)
                                    and assertion.get("identifier")
                                    and assertion.get("referent_id")
                                    and assertion.get("valid_from")
                                    and "valid_to" in assertion
                                    and assertion.get("assertion_source")
                                    for assertion in metadata["identifier_assertions"]
                                )
                            ),
                            "covers_admin_water_world": bool(
                                isinstance(metadata.get("world_partition"), dict)
                                and metadata["world_partition"].get("world_id")
                                and metadata["world_partition"].get("surface_class")
                                in {"land", "water"}
                                and metadata["world_partition"].get("coverage_complete")
                                is True
                                and metadata["world_partition"].get("gap_count") == 0
                                and metadata["world_partition"].get("overlap_count") == 0
                                and metadata["world_partition"].get("partition_rule")
                                and metadata["world_partition"].get("release_id")
                            ),
                            "derives_release_scale_hints": bool(
                                isinstance(metadata.get("scale_hint"), dict)
                                and metadata["scale_hint"].get("purpose")
                                in {"zoom", "label_priority", "aggregation", "comparison"}
                                and metadata["scale_hint"].get("method")
                                and metadata["scale_hint"].get("input_release_id")
                                and metadata["scale_hint"].get("output_release_id")
                                and metadata["scale_hint"].get("source_native_level") is not None
                                and metadata["scale_hint"].get("field_status") == "derived"
                                and metadata["scale_hint"].get("affects_identity") is False
                            ),
                            "derives_shaped_sibling_area_depth": _valid_shaped_sibling_area_depth(
                                metadata.get("sibling_area_depth")
                            ),
                            "isolates_customer_world_branches": bool(
                                isinstance(metadata.get("world_branch"), dict)
                                and metadata["world_branch"].get("world_id")
                                and metadata["world_branch"].get("branch_id")
                                and metadata["world_branch"].get("base_release_id")
                                and metadata["world_branch"].get("namespace_scope")
                                and metadata["world_branch"].get("resolution_scope")
                                == "world_and_branch"
                                and metadata["world_branch"].get("branch_isolated") is True
                                and metadata["world_branch"].get("official_unchanged") is True
                                and metadata["world_branch"].get("merge_policy")
                                == "explicit_reviewed_promotion"
                            ),
                            "pins_family_authority": bool(
                                isinstance(metadata.get("authority_selection"), dict)
                                and metadata["authority_selection"].get("family_id")
                                and metadata["authority_selection"].get("authority_id")
                                and metadata["authority_selection"].get("authority_release_id")
                                and metadata["authority_selection"].get("source_artifact_id")
                                and metadata["authority_selection"].get("effective_at")
                                and metadata["authority_selection"].get("adopted_at")
                                and metadata["authority_selection"].get("selection_policy")
                                == "declared_family_authority"
                                and metadata["authority_selection"].get("official_view_deterministic")
                                is True
                                and metadata["authority_selection"].get("latest_wins") is False
                                and metadata["authority_selection"].get("alternates_preserved") is True
                            ),
                            "declares_geometry_distribution": bool(
                                isinstance(metadata.get("geometry_distribution"), dict)
                                and metadata["geometry_distribution"].get("profile") == "geometry"
                                and metadata["geometry_distribution"].get("schema_version")
                                and metadata["geometry_distribution"].get("access_posture")
                                in {"public", "customer_world", "restricted"}
                                and metadata["geometry_distribution"].get("display_precision")
                                and metadata["geometry_distribution"].get("export_precision")
                                and metadata["geometry_distribution"].get("generalization_method")
                                and metadata["geometry_distribution"].get("license")
                                and metadata["geometry_distribution"].get("attribution")
                                and metadata["geometry_distribution"].get("privacy_review")
                                and metadata["geometry_distribution"].get("world_id")
                                and metadata["geometry_distribution"].get("branch_id")
                                and metadata["geometry_distribution"].get("data_profile_inherited")
                                is False
                            ),
                            "reproduces_confidence_supersession": bool(
                                isinstance(metadata.get("confidence_supersession"), dict)
                                and metadata["confidence_supersession"].get("relationship_method")
                                and metadata["confidence_supersession"].get("relationship_source")
                                and metadata["confidence_supersession"].get("algorithm_version")
                                and metadata["confidence_supersession"].get("threshold_version")
                                and "score" in metadata["confidence_supersession"]
                                and metadata["confidence_supersession"].get("score_semantics")
                                and metadata["confidence_supersession"].get("supersession_status")
                                in {"candidate", "confirmed", "none"}
                                and isinstance(
                                    metadata["confidence_supersession"].get("successor_ids"), list
                                )
                                and metadata["confidence_supersession"].get("evidence_artifact_id")
                                and metadata["confidence_supersession"].get("release_id")
                                and metadata["confidence_supersession"].get("default_score_used")
                                is False
                            ),
                            "preserves_multiaxial_time": all(
                                metadata.get(field)
                                for field in ("effective_at", "published_at", "adopted_at")
                            ),
                            "supports_pinnable_release": bool(
                                isinstance(release, dict)
                                and release.get("geography_release_id")
                                and release.get("components")
                                and release.get("content_hash")
                            ),
                            "hashes_artifacts_not_referents": bool(
                                metadata.get("referent_id")
                                and metadata.get("artifact_id")
                                and metadata.get("artifact_content_hash")
                                and metadata.get("referent_id") != metadata.get("artifact_content_hash")
                            ),
                            "preserves_relationship_provenance": bool(
                                metadata.get("relationship_method")
                                and metadata.get("relationship_source")
                                and metadata.get("reproducibility")
                            ),
                            "guards_same_as": bool(
                                edge_type
                                and (
                                    edge_type != "same_as"
                                    or (
                                        metadata.get("identity_confidence") is not None
                                        and metadata.get("relationship_source")
                                    )
                                )
                            ),
                            "prefers_direct_crosswalk": metadata.get("crosswalk_selection_policy")
                            == "direct_authoritative_then_admin_pivot",
                            "declares_pack_projection": metadata.get("pack_projection")
                            in {"source_era_primary", "present_allocation_explicit"},
                        }
                        missing_evidence = sorted(
                            field
                            for field, supported in required_metadata.items()
                            if stewardship_oracle.get(field) is True and not supported
                        )
                        if missing_evidence:
                            errors.append(
                                {
                                    "code": "MISSING_STEWARDSHIP_EVIDENCE",
                                    "index": index,
                                    "case": case.get("case"),
                                    "fields": missing_evidence,
                                }
                            )
    if missing_case_names:
        errors.append({"code": "MISSING_CASE_NAME", "indexes": missing_case_names})
    if missing_identifiers:
        errors.append({"code": "MISSING_IDENTIFIER", "indexes": missing_identifiers})
    duplicate_cases = sorted(name for name, count in case_counts.items() if name and count > 1)
    duplicate_ids = sorted(identifier for identifier, count in id_counts.items() if identifier and count > 1)
    if duplicate_cases:
        errors.append({"code": "DUPLICATE_CASE_NAME", "values": duplicate_cases})
    if duplicate_ids:
        errors.append({"code": "DUPLICATE_IDENTIFIER", "values": duplicate_ids})
    if doctrine_override_cases:
        warnings.append(
            {"code": "LEGACY_DOCTRINE_EXPECTATIONS", "case_count": len(doctrine_override_cases)}
        )
    if legacy_expectation_cases:
        warnings.append(
            {"code": "LEGACY_FLAT_EXPECTATIONS", "case_count": len(legacy_expectation_cases)}
        )
    return {
        "case_count": len(cases),
        "oracle_fingerprint": oracle_fingerprint(cases),
        "errors": errors,
        "warnings": warnings,
        "valid": not errors,
        "oracle_coverage": {
            "explicit_declared_cases": explicit_declared,
            "explicit_raw_cases": explicit_raw,
            "explicit_designation_cases": explicit_designation,
            "explicit_stewardship_cases": explicit_stewardship,
            "declared_scored_cases": declared_scored,
            "raw_scored_cases": raw_scored,
            "designation_scored_cases": designation_scored,
            "stewardship_scored_cases": stewardship_scored,
        },
        "legacy_doctrine_override_cases": doctrine_override_cases,
        "legacy_doctrine_override_case_count": len(doctrine_override_cases),
        "legacy_expectation_cases": legacy_expectation_cases,
        "legacy_expectation_case_count": len(legacy_expectation_cases),
    }


def doctrine_scorecard(cases: list[dict[str, Any]], *, doctrine: str | None = None) -> dict[str, Any]:
    """Return doctrine-neutral correctness and separate simplicity measurements."""
    doctrine_name = str(doctrine or "proposed_changes")
    dual_results = evaluate_dual_mode_cases(cases, doctrine=doctrine_name)
    declared = [result["declared"] for result in dual_results]
    raw = [result["raw"] for result in dual_results]
    declared_assertions = sum(result["oracle_assertions"] for result in declared)
    declared_assertions_passed = sum(result["oracle_assertions_passed"] for result in declared)
    raw_assertions = sum(result["oracle_assertions"] for result in raw)
    raw_assertions_passed = sum(result["oracle_assertions_passed"] for result in raw)
    designation = evaluate_designation_cases(cases, doctrine=doctrine_name)
    designation_assertions = sum(result["oracle_assertions"] for result in designation)
    designation_assertions_passed = sum(
        result["oracle_assertions_passed"] for result in designation
    )
    stewardship = evaluate_stewardship_cases(cases, doctrine=doctrine_name)
    stewardship_assertions = sum(result["oracle_assertions"] for result in stewardship)
    stewardship_assertions_passed = sum(
        result["oracle_assertions_passed"] for result in stewardship
    )
    audit = registry_audit(cases, doctrine=doctrine_name)
    return {
        "doctrine": doctrine_name,
        "doctrine_fingerprint": doctrine_manifest(doctrine_name)["fingerprint"],
        "oracle_fingerprint": oracle_fingerprint(cases),
        "case_count": len(cases),
        "declared": {
            "scored_cases": sum(bool(result["oracle"]["scored"]) for result in declared),
            "unscored_cases": sum(not result["oracle"]["scored"] for result in declared),
            "oracle_assertions": declared_assertions,
            "oracle_assertions_passed": declared_assertions_passed,
            "assertion_accuracy": (
                round(declared_assertions_passed / declared_assertions, 6)
                if declared_assertions
                else None
            ),
            "clean_scored_cases": sum(
                bool(result["oracle"]["scored"]) and bool(result["clean"])
                for result in declared
            ),
            "known_issue_cases": sum(bool(result["known_findings"]) for result in declared),
            "unexpected_issue_cases": sum(bool(result["unexpected_findings"]) for result in declared),
            "resolved_known_issue_count": sum(len(result["resolved_known_issues"]) for result in declared),
            "open_policy_case_count": sum(bool(result["oracle"]["open_policy_fields"]) for result in declared),
        },
        "raw": {
            "scored_cases": sum(bool(result["oracle"]["scored"]) for result in raw),
            "unscored_cases": sum(not result["oracle"]["scored"] for result in raw),
            "oracle_assertions": raw_assertions,
            "oracle_assertions_passed": raw_assertions_passed,
            "assertion_accuracy": round(raw_assertions_passed / raw_assertions, 6) if raw_assertions else None,
            "declared_delta_cases": sum(bool(result["deltas"]) for result in dual_results),
        },
        "designation": {
            "case_count": len(designation),
            "scored_cases": sum(bool(result["oracle"]["scored"]) for result in designation),
            "unscored_cases": sum(not result["oracle"]["scored"] for result in designation),
            "oracle_assertions": designation_assertions,
            "oracle_assertions_passed": designation_assertions_passed,
            "assertion_accuracy": (
                round(designation_assertions_passed / designation_assertions, 6)
                if designation_assertions
                else None
            ),
            "clean_scored_cases": sum(
                bool(result["oracle"]["scored"]) and bool(result["gate_ok"])
                for result in designation
            ),
            "oracle_failure_cases": sum(result["signal"] == "oracle_failure" for result in designation),
        },
        "stewardship": {
            "case_count": len(stewardship),
            "scored_cases": sum(bool(result["oracle"]["scored"]) for result in stewardship),
            "unscored_cases": sum(not result["oracle"]["scored"] for result in stewardship),
            "oracle_assertions": stewardship_assertions,
            "oracle_assertions_passed": stewardship_assertions_passed,
            "assertion_accuracy": (
                round(stewardship_assertions_passed / stewardship_assertions, 6)
                if stewardship_assertions
                else None
            ),
            "clean_scored_cases": sum(
                bool(result["oracle"]["scored"]) and bool(result["gate_ok"])
                for result in stewardship
            ),
            "oracle_failure_cases": sum(
                result["signal"] == "oracle_failure" for result in stewardship
            ),
        },
        "registry": {
            "recognized_cases": audit["recognized_cases"],
            "overlap_count": audit["overlap_count"],
            "specific_collision_count": audit["specific_collision_count"],
            "unused_namespace_rule_count": len(audit["unused_namespace_rules"]),
        },
        "complexity": doctrine_manifest(doctrine_name)["complexity"],
        "gate_ok": all(bool(result["gate_ok"]) for result in dual_results)
        and all(bool(result["gate_ok"]) for result in designation)
        and all(bool(result["gate_ok"]) for result in stewardship),
    }
