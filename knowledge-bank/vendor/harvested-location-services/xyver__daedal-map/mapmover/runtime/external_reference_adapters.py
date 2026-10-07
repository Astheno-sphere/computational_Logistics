"""Admitted typed bridges from independent external ids to ``loc_id``.

An external system touches ``loc_id`` only through one fingerprint-pinned,
publication-admitted, bidirectional crosswalk. Only ``equivalent_identity``
edges may recommend a loc_id; containment and overlap remain relationships.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from ..duckdb_helpers import is_cloud_mode, path_to_uri, quote_ident, run_df
from ..paths import DATA_ROOT

ADMITTED_STATES = frozenset({"admitted", "published", "active"})
GERS_SYSTEM = "overture_gers"


@dataclass(frozen=True)
class ExternalReferenceAdapter:
    system: str
    label: str
    aliases: tuple[str, ...]
    identifier_pattern: str
    pointer_path: str
    external_id_column: str
    internal_id_column: str
    source_release_column: str
    internal_release_column: str
    country_column: str
    relationship_column: str = "relationship_type"
    primary_column: str = "is_primary"
    source_level_column: str = "admin_level"
    external_subtype_column: str = "overture_subtype"
    identity_confidence_column: str = "identity_confidence"
    geometry_confidence_column: str = "geometry_confidence"
    external_name_column: str = "overture_name"
    internal_name_column: str = "loc_name"


@dataclass(frozen=True)
class ExternalReferencePartition:
    partition_id: str
    forward_path: str
    forward_sha256: str
    reverse_path: str
    reverse_sha256: str
    source_release: str
    internal_release: str
    country: str


@dataclass(frozen=True)
class AdmittedExternalBridge:
    adapter: ExternalReferenceAdapter
    release_fingerprint: str
    source_release: str
    partitions: tuple[ExternalReferencePartition, ...]
    source_license: dict[str, Any]
    runtime_path: str | None = None
    runtime_sha256: str | None = None


@dataclass(frozen=True)
class ExternalReferenceEdge:
    external_id: str
    loc_id: str
    relationship_type: str
    is_primary: bool
    source_release: str | None
    internal_release: str | None
    country: str | None
    source_level: int | None
    external_subtype: str | None
    identity_confidence: str | None
    geometry_confidence: float | None
    external_name: str | None
    loc_name: str | None
    edge_id: str | None = None
    partition_id: str | None = None
    bridge_generation_id: str | None = None
    edge_content_hash: str | None = None

    @property
    def is_equivalence(self) -> bool:
        return self.relationship_type == "equivalent_identity"


_ADAPTERS = {
    GERS_SYSTEM: ExternalReferenceAdapter(
        system=GERS_SYSTEM,
        label="Overture Maps GERS division id",
        aliases=(
            "gers", "gers_id", "overture", "overture_id", "overture_division",
            "overture_divisions", "overture_division_id", "overture_maps",
            "overture_gers_county", "overture_gers_region",
        ),
        identifier_pattern=r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
        pointer_path="geometry/bridges/GERS/index.json",
        external_id_column="gers_division_id",
        internal_id_column="loc_id",
        source_release_column="overture_release",
        internal_release_column="spine_vintage",
        country_column="iso3",
    ),
}

_ADAPTER_FIELDS = {
    "external_id_column", "internal_id_column", "source_release_column",
    "internal_release_column", "country_column", "relationship_column",
    "primary_column", "source_level_column", "external_subtype_column",
    "identity_confidence_column", "geometry_confidence_column",
    "external_name_column", "internal_name_column",
}


def _normalized_system(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _adapter_from_catalog_record(record: dict[str, Any]) -> ExternalReferenceAdapter | None:
    spec = record.get("adapter") if isinstance(record.get("adapter"), dict) else {}
    system = _normalized_system(record.get("external_system"))
    pattern = str(spec.get("identifier_pattern") or "").strip()
    columns = spec.get("columns") if isinstance(spec.get("columns"), dict) else {}
    required = {"external_id_column", "internal_id_column", "source_release_column",
                "internal_release_column", "country_column"}
    if not re.fullmatch(r"[a-z][a-z0-9_]*", system) or not pattern or not required.issubset(columns):
        return None
    try:
        re.compile(pattern)
    except re.error:
        return None
    if len(pattern) > 512 or any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", str(value)) for value in columns.values()):
        return None
    pointer_path = "geometry/bridges/GERS/index.json" if system == GERS_SYSTEM else f"geometry/bridges/{system}/index.json"
    if spec.get("pointer_path", pointer_path) != pointer_path:
        return None
    aliases = spec.get("aliases") or []
    if not isinstance(aliases, list):
        return None
    values = {key: str(value) for key, value in columns.items() if key in _ADAPTER_FIELDS}
    return ExternalReferenceAdapter(
        system=system,
        label=str(spec.get("label") or system),
        aliases=tuple(
            alias for alias in (_normalized_system(value) for value in aliases)
            if alias and alias != system
        ),
        identifier_pattern=pattern,
        pointer_path=pointer_path,
        **values,
    )


def _catalog_adapters() -> dict[str, ExternalReferenceAdapter]:
    try:
        from .geometry_catalog import load_geometry_catalog
        records = load_geometry_catalog().get("external_reference_bridges") or []
    except Exception:
        return {}
    result: dict[str, ExternalReferenceAdapter] = {}
    for record in records:
        adapter = _adapter_from_catalog_record(record) if isinstance(record, dict) else None
        if adapter is not None:
            result[adapter.system] = adapter
    return result


def _all_adapters() -> dict[str, ExternalReferenceAdapter]:
    return {**_ADAPTERS, **_catalog_adapters()}


def normalize_external_system(value: Any) -> str:
    text = _normalized_system(value)
    for adapter in _all_adapters().values():
        if text == adapter.system or text in adapter.aliases:
            return adapter.system
    return text


def external_system_aliases() -> dict[str, str]:
    return {alias: adapter.system for adapter in _all_adapters().values() for alias in (adapter.system, *adapter.aliases)}


def get_external_adapter(system: Any) -> ExternalReferenceAdapter | None:
    return _all_adapters().get(normalize_external_system(system))


def admitted_external_adapters() -> list[ExternalReferenceAdapter]:
    return [adapter for adapter in _all_adapters().values() if admitted_bridge(adapter) is not None]


def identifier_matches(adapter: ExternalReferenceAdapter, value: str) -> bool:
    return bool(re.fullmatch(adapter.identifier_pattern, value))


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, ValueError):
        return {}


def _bounded_data_path(reference: Any) -> Path | None:
    text = str(reference or "").strip()
    if not text or Path(text).is_absolute():
        return None
    root = DATA_ROOT.resolve()
    candidate = (root / text).resolve()
    return candidate if candidate.is_relative_to(root) else None


def stable_fingerprint(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _release_fingerprint(manifest: dict[str, Any]) -> str:
    return stable_fingerprint({
        "external_system": manifest.get("external_system"),
        "external_release": manifest.get("external_release"),
        "adapter": manifest.get("adapter") or {},
        "partitions": manifest.get("partitions") or [],
    })


def _publication_admitted(manifest: dict[str, Any]) -> bool:
    publication = manifest.get("publication") if isinstance(manifest.get("publication"), dict) else {}
    return (
        str(manifest.get("status") or "") in ADMITTED_STATES
        and str(manifest.get("publication_state") or publication.get("state") or "") in ADMITTED_STATES
        and publication.get("hosted_publication_cleared") is True
    )


def _catalog_record(adapter: ExternalReferenceAdapter) -> tuple[dict[str, Any], bool]:
    try:
        from .geometry_catalog import load_geometry_catalog
        matching = [
            row for row in load_geometry_catalog().get("external_reference_bridges") or []
            if isinstance(row, dict) and _normalized_system(row.get("external_system")) == adapter.system
        ]
    except Exception:
        matching = []
    admitted = next((row for row in matching if _publication_admitted(row)), {})
    return admitted, bool(matching and not admitted)


def _local_release(adapter: ExternalReferenceAdapter) -> dict[str, Any]:
    pointer_path = _bounded_data_path(adapter.pointer_path)
    pointer = _load_json(pointer_path) if pointer_path else {}
    if pointer.get("profile") != "external_reference_bridge_pointer":
        return {}
    manifest_path = _bounded_data_path(pointer.get("release_manifest"))
    manifest = _load_json(manifest_path) if manifest_path else {}
    declared = str(manifest.get("release_fingerprint") or "")
    if (
        manifest.get("profile") != "external_reference_bridge"
        or str(pointer.get("release_fingerprint") or "") != declared
        or _release_fingerprint(manifest) != declared
    ):
        return {}
    runtime_manifest_path = _bounded_data_path(pointer.get("runtime_manifest"))
    runtime_manifest = _load_json(runtime_manifest_path) if runtime_manifest_path else {}
    runtime_artifact = (
        runtime_manifest.get("artifact")
        if isinstance(runtime_manifest.get("artifact"), dict) else {}
    )
    if (
        runtime_manifest.get("profile") == "external_reference_bridge_compact_runtime"
        and runtime_manifest.get("bridge_release_fingerprint") == declared
        and runtime_artifact.get("path")
        and runtime_artifact.get("sha256")
    ):
        manifest = {**manifest, "runtime_layout": "compact_parquet", "runtime_artifact": runtime_artifact}
    return manifest


def _partition_manifest(record: dict[str, Any]) -> dict[str, Any]:
    if isinstance(record.get("artifacts"), dict):
        return record
    reference = str(record.get("manifest_path") or "").strip()
    manifest_path = _bounded_data_path(reference)
    manifest = _load_json(manifest_path) if manifest_path else {}
    if manifest.get("profile") != "external_reference_bridge_partition":
        return {}
    ignored = {"schema_version", "profile", "row_count", "bidirectional", "has_shapes", "schema", "partition_fingerprint"}
    identity = {key: value for key, value in manifest.items() if key not in ignored}
    declared = str(record.get("partition_fingerprint") or manifest.get("partition_fingerprint") or "")
    return manifest if stable_fingerprint(identity) == declared else {}


def _normalize_partition(record: dict[str, Any], source_release: str) -> ExternalReferencePartition | None:
    manifest = _partition_manifest(record)
    artifacts = manifest.get("artifacts") if isinstance(manifest.get("artifacts"), dict) else {}
    forward = artifacts.get("by_external_id") if isinstance(artifacts.get("by_external_id"), dict) else {}
    reverse = artifacts.get("by_internal_id") if isinstance(artifacts.get("by_internal_id"), dict) else {}
    partition_id = str(record.get("partition_fingerprint") or manifest.get("partition_fingerprint") or "").strip()
    internal = str(manifest.get("internal_spine_release") or record.get("internal_spine_release") or "").strip()
    country = str(manifest.get("country_iso3") or record.get("country_iso3") or "").strip().upper()
    required = (partition_id, internal, country, forward.get("path"), forward.get("sha256"), reverse.get("path"), reverse.get("sha256"))
    if not all(required):
        return None
    return ExternalReferencePartition(
        partition_id=partition_id,
        forward_path=str(forward["path"]), forward_sha256=str(forward["sha256"]).lower(),
        reverse_path=str(reverse["path"]), reverse_sha256=str(reverse["sha256"]).lower(),
        source_release=source_release, internal_release=internal, country=country,
    )


def admitted_bridge(adapter: ExternalReferenceAdapter) -> AdmittedExternalBridge | None:
    catalog, catalog_blocks = _catalog_record(adapter)
    if catalog_blocks:
        return None
    manifest = catalog if is_cloud_mode() and catalog else _local_release(adapter)
    if not manifest or not _publication_admitted(manifest):
        return None
    fingerprint = str(manifest.get("release_fingerprint") or "")
    compact_runtime = (
        manifest.get("runtime_layout") == "compact_parquet"
        and isinstance(manifest.get("runtime_artifact"), dict)
    )
    if not compact_runtime and _release_fingerprint(manifest) != fingerprint:
        return None
    source_release = str(manifest.get("external_release") or manifest.get("active_release") or "").strip()
    partitions = tuple(
        partition for record in manifest.get("partitions") or []
        if isinstance(record, dict) and (partition := _normalize_partition(record, source_release)) is not None
    )
    if (
        not compact_runtime
        and (not partitions or len({partition.partition_id for partition in partitions}) != len(partitions))
    ):
        return None
    runtime = manifest.get("runtime_artifact") if isinstance(manifest.get("runtime_artifact"), dict) else {}
    runtime_path = str(runtime.get("path") or "").strip() or None
    runtime_sha256 = str(runtime.get("sha256") or "").strip().lower() or None
    if bool(runtime_path) != bool(runtime_sha256):
        return None
    return AdmittedExternalBridge(
        adapter=adapter, release_fingerprint=fingerprint, source_release=source_release,
        partitions=partitions, source_license=dict(manifest.get("source_license") or {}),
        runtime_path=runtime_path, runtime_sha256=runtime_sha256,
    )


@lru_cache(maxsize=256)
def _verified_file(path_text: str, expected: str, size: int, modified_ns: int) -> bool:
    digest = hashlib.sha256()
    try:
        with Path(path_text).open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return False
    return digest.hexdigest() == expected


def _artifact_verified(relative: str, expected: str) -> bool:
    path = _bounded_data_path(relative)
    if path is None or not path.is_file() or not re.fullmatch(r"[0-9a-f]{64}", expected):
        return False
    try:
        stat = path.stat()
    except OSError:
        return False
    return _verified_file(str(path.resolve()), expected, stat.st_size, stat.st_mtime_ns)


def _selected_partitions(
    bridge: AdmittedExternalBridge, *, source_release: str | None = None,
    internal_release: str | None = None, country_scope: str | None = None,
) -> tuple[ExternalReferencePartition, ...]:
    source = str(source_release or "").strip()
    internal = str(internal_release or "").strip()
    country = str(country_scope or "").strip().upper()
    return tuple(
        partition for partition in bridge.partitions
        if (not source or partition.source_release == source)
        and (not internal or partition.internal_release == internal)
        and (not country or partition.country == country)
    )


def adapter_available(adapter: ExternalReferenceAdapter) -> bool:
    bridge = admitted_bridge(adapter)
    return _bridge_available(bridge)


def _bridge_available(bridge: AdmittedExternalBridge | None) -> bool:
    if bridge is None:
        return False
    if is_cloud_mode():
        return True
    if bridge.runtime_path and bridge.runtime_sha256:
        return _artifact_verified(bridge.runtime_path, bridge.runtime_sha256)
    return all(
        _artifact_verified(partition.forward_path, partition.forward_sha256)
        and _artifact_verified(partition.reverse_path, partition.reverse_sha256)
        for partition in bridge.partitions
    )


def _value(row: dict[str, Any], key: str) -> Any:
    value = row.get(key)
    return None if value is None or str(value).strip().lower() in {"", "nan", "nat", "<na>"} else value


def _edge(adapter: ExternalReferenceAdapter, row: dict[str, Any], partition: ExternalReferencePartition | None) -> ExternalReferenceEdge:
    raw_relationship = str(_value(row, adapter.relationship_column) or "overlaps").lower()
    relationship = {
        "equivalence": "equivalent_identity", "equivalent": "equivalent_identity",
        "identity": "equivalent_identity", "part_of": "contained_by", "overlap": "overlaps",
    }.get(raw_relationship, raw_relationship)
    try:
        level = int(_value(row, adapter.source_level_column))
    except (TypeError, ValueError):
        level = None
    try:
        geometry_confidence = float(_value(row, adapter.geometry_confidence_column))
    except (TypeError, ValueError):
        geometry_confidence = None
    return ExternalReferenceEdge(
        external_id=str(_value(row, adapter.external_id_column) or ""),
        loc_id=str(_value(row, adapter.internal_id_column) or ""),
        relationship_type=relationship, is_primary=bool(_value(row, adapter.primary_column)),
        source_release=str(_value(row, adapter.source_release_column) or (partition.source_release if partition else "")).strip() or None,
        internal_release=str(_value(row, adapter.internal_release_column) or (partition.internal_release if partition else "")).strip() or None,
        country=str(_value(row, adapter.country_column) or (partition.country if partition else "")).strip().upper() or None,
        source_level=level,
        external_subtype=str(_value(row, adapter.external_subtype_column) or "").strip() or None,
        identity_confidence=str(_value(row, adapter.identity_confidence_column) or "").strip() or None,
        geometry_confidence=geometry_confidence,
        external_name=str(_value(row, adapter.external_name_column) or "").strip() or None,
        loc_name=str(_value(row, adapter.internal_name_column) or "").strip() or None,
        edge_id=str(_value(row, "edge_id") or "").strip() or None,
        partition_id=str(_value(row, "partition_id") or (partition.partition_id if partition else "")).strip() or None,
        bridge_generation_id=str(_value(row, "bridge_generation_id") or "").strip() or None,
        edge_content_hash=str(_value(row, "edge_content_hash") or "").strip() or None,
    )


def _query_edges(
    bridge: AdmittedExternalBridge, partitions: tuple[ExternalReferencePartition, ...],
    *, reverse: bool, values: list[str], source_release: str | None = None,
    internal_release: str | None = None, country_scope: str | None = None,
) -> list[ExternalReferenceEdge]:
    if not values or (not partitions and not bridge.runtime_path):
        return []
    adapter = bridge.adapter
    if bridge.runtime_path and bridge.runtime_sha256:
        paths = [bridge.runtime_path]
        hashes = [bridge.runtime_sha256]
    else:
        paths = [partition.reverse_path if reverse else partition.forward_path for partition in partitions]
        hashes = [partition.reverse_sha256 if reverse else partition.forward_sha256 for partition in partitions]
    if not is_cloud_mode() and not all(
        _artifact_verified(path, digest) for path, digest in zip(paths, hashes)
    ):
        return []
    uris = [path_to_uri(DATA_ROOT / path) for path in paths]
    column = adapter.internal_id_column if reverse else adapter.external_id_column
    clauses = [f"{quote_ident(column)} IN ({', '.join('?' for _ in values)})"]
    parameters: list[Any] = [uris, *values]
    for value, filter_column in (
        (source_release, adapter.source_release_column),
        (internal_release, adapter.internal_release_column),
        (str(country_scope or "").strip().upper() or None, adapter.country_column),
    ):
        if value:
            clauses.append(f"{quote_ident(filter_column)} = ?")
            parameters.append(value)
    sql = (
        "SELECT * FROM read_parquet(?, union_by_name=true, filename=true) WHERE "
        + " AND ".join(clauses)
    )
    try:
        frame = run_df(sql, parameters)
    except Exception:
        return []
    by_uri = {str(uri): partition for uri, partition in zip(uris, partitions)}
    return [
        _edge(adapter, row, by_uri.get(str(row.get("filename") or "")))
        for row in ([] if frame is None else frame.to_dict("records"))
    ]


def lookup_external_edges(
    system: str, external_id: str, *, source_release: str | None = None,
    internal_release: str | None = None, country_scope: str | None = None,
) -> list[ExternalReferenceEdge]:
    adapter = get_external_adapter(system)
    bridge = admitted_bridge(adapter) if adapter else None
    if not _bridge_available(bridge):
        return []
    assert bridge is not None
    partitions = _selected_partitions(bridge, source_release=source_release, internal_release=internal_release, country_scope=country_scope)
    return _query_edges(
        bridge, partitions, reverse=False, values=[str(external_id).strip()],
        source_release=source_release, internal_release=internal_release,
        country_scope=country_scope,
    )


def lookup_external_edges_batch(
    system: str,
    external_ids: list[str],
    *,
    source_release: str | None = None,
    internal_release: str | None = None,
    country_scope: str | None = None,
) -> dict[str, list[ExternalReferenceEdge]] | None:
    """Resolve many external IDs with one query over the selected partitions.

    ``None`` means the bridge is unavailable. An available bridge returns an
    entry for every distinct non-empty input, including identifiers with no
    matching edge.
    """
    adapter = get_external_adapter(system)
    bridge = admitted_bridge(adapter) if adapter else None
    if not _bridge_available(bridge):
        return None
    assert bridge is not None
    requested = list(dict.fromkeys(
        str(value).strip() for value in external_ids if str(value).strip()
    ))
    partitions = _selected_partitions(
        bridge,
        source_release=source_release,
        internal_release=internal_release,
        country_scope=country_scope,
    )
    grouped: dict[str, list[ExternalReferenceEdge]] = {value: [] for value in requested}
    for edge in _query_edges(
        bridge, partitions, reverse=False, values=requested,
        source_release=source_release, internal_release=internal_release,
        country_scope=country_scope,
    ):
        grouped.setdefault(edge.external_id, []).append(edge)
    return grouped


def lookup_loc_id_edges(
    system: str, loc_id: str, *, source_release: str | None = None,
    internal_release: str | None = None, country_scope: str | None = None,
    limit: int | None = 100,
) -> list[ExternalReferenceEdge]:
    adapter = get_external_adapter(system)
    bridge = admitted_bridge(adapter) if adapter else None
    if not _bridge_available(bridge):
        return []
    assert bridge is not None
    partitions = _selected_partitions(bridge, source_release=source_release, internal_release=internal_release, country_scope=country_scope)
    edges = _query_edges(
        bridge, partitions, reverse=True, values=[str(loc_id).strip()],
        source_release=source_release, internal_release=internal_release,
        country_scope=country_scope,
    )
    edges.sort(key=lambda edge: (not edge.is_equivalence, -(edge.geometry_confidence or 0.0), edge.external_id))
    return edges if limit is None else edges[:max(0, int(limit))]


def lookup_loc_id_edges_batch(
    system: str,
    loc_ids: list[str],
    *,
    source_release: str | None = None,
    internal_release: str | None = None,
    country_scope: str | None = None,
    limit: int | None = 100,
) -> dict[str, list[ExternalReferenceEdge]] | None:
    """Resolve many loc_ids through one reverse bridge-partition query."""
    adapter = get_external_adapter(system)
    bridge = admitted_bridge(adapter) if adapter else None
    if not _bridge_available(bridge):
        return None
    assert bridge is not None
    requested = list(dict.fromkeys(
        str(value).strip() for value in loc_ids if str(value).strip()
    ))
    partitions = _selected_partitions(
        bridge,
        source_release=source_release,
        internal_release=internal_release,
        country_scope=country_scope,
    )
    grouped: dict[str, list[ExternalReferenceEdge]] = {value: [] for value in requested}
    for edge in _query_edges(
        bridge, partitions, reverse=True, values=requested,
        source_release=source_release, internal_release=internal_release,
        country_scope=country_scope,
    ):
        grouped.setdefault(edge.loc_id, []).append(edge)
    maximum = None if limit is None else max(0, int(limit))
    for loc_id, edges in grouped.items():
        edges.sort(key=lambda edge: (not edge.is_equivalence, -(edge.geometry_confidence or 0.0), edge.external_id))
        if maximum is not None:
            grouped[loc_id] = edges[:maximum]
    return grouped


def external_equivalence_matches(
    system: str, values: list[str], *, country_scope: str | None = None,
    source_release: str | None = None, internal_release: str | None = None,
) -> dict[str, Any]:
    adapter = get_external_adapter(system)
    bridge = admitted_bridge(adapter) if adapter else None
    requested = list(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))
    if not _bridge_available(bridge) or not requested:
        return {"matches": {}, "source_releases": [], "internal_releases": []}
    assert bridge is not None
    partitions = _selected_partitions(bridge, source_release=source_release, internal_release=internal_release, country_scope=country_scope)
    equivalences = [
        edge for edge in _query_edges(
            bridge, partitions, reverse=False, values=requested,
            source_release=source_release, internal_release=internal_release,
            country_scope=country_scope,
        ) if edge.is_equivalence
    ]
    matches: dict[str, list[str]] = {}
    for edge in equivalences:
        matches.setdefault(edge.external_id, []).append(edge.loc_id)
    return {
        "matches": {key: list(dict.fromkeys(loc_ids)) for key, loc_ids in matches.items()},
        "source_releases": sorted({edge.source_release for edge in equivalences if edge.source_release}),
        "internal_releases": sorted({edge.internal_release for edge in equivalences if edge.internal_release}),
        "countries": sorted({edge.country for edge in equivalences if edge.country}),
        "source_levels": sorted({edge.source_level for edge in equivalences if edge.source_level is not None}),
    }


def external_primary_loc_ids(
    system: str, values: list[str], *, country_scope: str | None = None,
    source_release: str | None = None, internal_release: str | None = None,
) -> dict[str, list[str]]:
    return external_equivalence_matches(
        system, values, country_scope=country_scope, source_release=source_release,
        internal_release=internal_release,
    )["matches"]


def adapter_public_entry(adapter: ExternalReferenceAdapter) -> dict[str, Any]:
    bridge = admitted_bridge(adapter)
    if bridge is None:
        return {}
    return {
        "system": adapter.system, "label": adapter.label,
        "role": "external_reference_bridge",
        "capabilities": ["exact_external_key_lookup", "typed_relationship_edges", "bidirectional_reference_lookup"],
        "resolver": "typed_external_reference_edges", "bidirectional": True,
        "target_admin_level_input": False,
        "release_fingerprint": bridge.release_fingerprint,
        "source_release": bridge.source_release,
        "internal_releases": sorted({partition.internal_release for partition in bridge.partitions}),
        "countries": sorted({partition.country for partition in bridge.partitions}),
        "partition_count": len(bridge.partitions),
        "license": bridge.source_license,
        "level_note": "External subtypes and observed levels are metadata, not a join key for target admin levels.",
    }


def edge_dict(edge: ExternalReferenceEdge) -> dict[str, Any]:
    return asdict(edge)
