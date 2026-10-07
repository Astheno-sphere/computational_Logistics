"""
Build catalog.json and index.json files from all metadata.json files.

Scans a data folder for metadata.json files in the standard structure:
  - global/{source_id}/metadata.json
  - global/un_sdg/{goal_id}/metadata.json
  - global/disasters/{type}/metadata.json
  - countries/{ISO3}/{source_id}/metadata.json

Outputs:
  - catalog.json: Summary of all sources for the app
  - index.json: Root data router pointing to all scopes

Usage:
    python converters/catalog_builder.py <data_folder>
    python converters/catalog_builder.py data/
    python converters/catalog_builder.py /path/to/county-map-data --catalog-only
    python converters/catalog_builder.py data/ --indexes-only
"""

import json
import argparse
from pathlib import Path
from datetime import date


def _build_coverage_description(geo: dict) -> str:
    """Build human-readable coverage description for LLM context."""
    if not geo:
        return "Unknown coverage"

    coverage_type = geo.get("type", "unknown")
    common_count = geo.get("common_count", 0)
    common_missing = geo.get("common_missing", [])
    region_coverage = geo.get("region_coverage", {})
    n_countries = geo.get("countries", 0)

    # Single country
    if coverage_type == "country":
        return "Single country"

    # Global coverage - use exclusion-based description
    if coverage_type == "global":
        parts = []
        for region in ["Africa", "Americas", "Asia", "Europe", "Oceania"]:
            if region in region_coverage:
                rc = region_coverage[region]
                parts.append(f"{region}: {rc['count']}/{rc['total']}")

        if common_count == 200:
            coverage = "All 200 common countries"
        elif common_count and len(common_missing) <= 10:
            coverage = f"{common_count}/200 common (missing {len(common_missing)})"
        elif common_count:
            coverage = f"{common_count}/200 common"
        else:
            coverage = "Global"

        if parts:
            return f"{coverage}. {', '.join(parts)}"
        return coverage

    # Regional coverage
    if region_coverage:
        parts = []
        for region, rc in region_coverage.items():
            parts.append(f"{region}: {rc['count']}/{rc['total']}")
        return ", ".join(parts)

    if n_countries:
        return f"{n_countries} countries"
    return "Unknown coverage"


def _trim_geographic_coverage(geo: dict) -> dict:
    """Trim geographic coverage for catalog (remove verbose lists)."""
    if not geo:
        return {}

    return {
        "type": geo.get("type"),
        "countries": geo.get("countries"),
        "common_count": geo.get("common_count"),
        "common_missing": geo.get("common_missing", []),
        "uncommonly_included": geo.get("uncommonly_included", []),
        "region_coverage": geo.get("region_coverage", {})
    }


def _trim_metrics(metrics: dict) -> dict:
    """Trim metrics for catalog (key info only, no by_era details)."""
    if not metrics:
        return {}

    trimmed = {}
    for key, m in metrics.items():
        trimmed[key] = {
            "name": m.get("name"),
            "unit": m.get("unit"),
            "years": m.get("years"),
            "countries": m.get("countries"),
            "density": m.get("density")
        }
    return trimmed


def _find_all_metadata_files(data_root: Path) -> list:
    """
    Find all metadata.json files in the standard folder structure.

    Returns list of tuples: (metadata_path, relative_path_for_catalog)
    """
    results = []

    # Global sources: global/{source_id}/metadata.json
    global_dir = data_root / "global"
    if global_dir.exists():
        for source_dir in sorted(global_dir.iterdir()):
            if not source_dir.is_dir():
                continue
            # Skip nested dirs handled separately
            if source_dir.name in ("un_sdg", "disasters"):
                continue
            meta_path = source_dir / "metadata.json"
            if meta_path.exists():
                rel_path = f"global/{source_dir.name}"
                results.append((meta_path, rel_path))

    # SDG goals: global/un_sdg/{goal_id}/metadata.json
    sdg_dir = data_root / "global" / "un_sdg"
    if sdg_dir.exists():
        for goal_dir in sorted(sdg_dir.iterdir()):
            if not goal_dir.is_dir():
                continue
            meta_path = goal_dir / "metadata.json"
            if meta_path.exists():
                rel_path = f"global/un_sdg/{goal_dir.name}"
                results.append((meta_path, rel_path))

    # Disaster sources: global/disasters/{type}/metadata.json
    disasters_dir = data_root / "global" / "disasters"
    if disasters_dir.exists():
        for disaster_dir in sorted(disasters_dir.iterdir()):
            if not disaster_dir.is_dir():
                continue
            meta_path = disaster_dir / "metadata.json"
            if meta_path.exists():
                rel_path = f"global/disasters/{disaster_dir.name}"
                results.append((meta_path, rel_path))

    # Country sources: countries/{country}/{source_id}/metadata.json
    countries_dir = data_root / "countries"
    if countries_dir.exists():
        for country_dir in sorted(countries_dir.iterdir()):
            if not country_dir.is_dir():
                continue
            for source_dir in sorted(country_dir.iterdir()):
                if not source_dir.is_dir():
                    continue
                meta_path = source_dir / "metadata.json"
                if meta_path.exists():
                    rel_path = f"countries/{country_dir.name}/{source_dir.name}"
                    results.append((meta_path, rel_path))

    return results


def build_catalog(data_root: Path, output_path: Path = None):
    """
    Scan all metadata.json files and build catalog.json.

    Args:
        data_root: Root data directory to scan.
        output_path: Path for catalog.json. Defaults to data_root/catalog.json.

    Returns:
        The catalog dict.
    """
    output_path = output_path or (data_root / "catalog.json")

    sources = []
    metadata_files = _find_all_metadata_files(data_root)

    print(f"Found {len(metadata_files)} metadata files\n")

    for meta_path, rel_path in metadata_files:
        print(f"  Adding: {rel_path}")

        with open(meta_path, encoding="utf-8") as f:
            metadata = json.load(f)

        # Extract summary for catalog
        geo = metadata.get("geographic_coverage", {})
        metrics = metadata.get("metrics", {})

        trimmed_geo = _trim_geographic_coverage(geo)
        trimmed_metrics = _trim_metrics(metrics)

        coverage_desc = metadata.get("coverage_description") or _build_coverage_description(geo)

        # Extract temporal info
        temp_coverage = metadata.get("temporal_coverage", {})
        temporal_info = {
            "start": temp_coverage.get("start"),
            "end": temp_coverage.get("end"),
            "granularity": temp_coverage.get("granularity", "yearly"),
            "field": temp_coverage.get("field", "year")
        }

        # Derive scope from path
        path_parts = rel_path.split("/")
        if path_parts[0] == "countries" and len(path_parts) >= 2:
            scope = path_parts[1].lower()
        else:
            scope = "global"

        sources.append({
            "source_id": metadata.get("source_id"),
            "source_name": metadata.get("source_name"),
            "pack_id": metadata.get("pack_id"),
            "category": metadata.get("category"),
            "data_type": metadata.get("data_type"),
            "scope": scope,
            "topic_tags": metadata.get("topic_tags", []),
            "keywords": metadata.get("keywords", []),
            "geographic_level": metadata.get("geographic_level"),
            "geographic_coverage": trimmed_geo,
            "coverage_description": coverage_desc,
            "temporal_coverage": temporal_info,
            "metrics": trimmed_metrics,
            "llm_summary": metadata.get("llm_summary", ""),
            "path": rel_path
        })

    catalog = {
        "catalog_version": "1.0",
        "last_updated": date.today().isoformat(),
        "total_sources": len(sources),
        "sources": sources
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2)

    print(f"\nCatalog saved: {output_path}")
    print(f"Total sources: {len(sources)}")

    return catalog


def _build_dataset_entry(data_root: Path, metadata: dict, rel_path: str) -> dict:
    """Build a dataset entry for index.json from metadata."""
    source_dir = data_root / rel_path
    parquets = list(source_dir.glob("*.parquet")) if source_dir.exists() else []

    # Classify parquet files
    files = {}
    for p in parquets:
        name = p.name.lower()
        if "event_areas" in name or "_areas" in name:
            files["event_areas"] = f"{rel_path.split('/')[-1]}/{p.name}"
        elif "events" in name:
            files["events"] = f"{rel_path.split('/')[-1]}/{p.name}"
        else:
            files["aggregates"] = f"{rel_path.split('/')[-1]}/{p.name}"

    entry = {
        "source_name": metadata.get("source_name"),
        "category": metadata.get("category", "general"),
        "files": files,
        "geographic_level": metadata.get("geographic_level", "unknown"),
        "has_coordinates": "events" in files or metadata.get("data_type") == "events"
    }

    tc = metadata.get("temporal_coverage", {})
    if tc.get("start") and tc.get("end"):
        entry["temporal_coverage"] = {
            "start": tc["start"],
            "end": tc["end"]
        }

    entry["record_counts"] = {
        "aggregates": metadata.get("row_count", 0)
    }
    if metadata.get("events_file"):
        entry["record_counts"]["events"] = metadata["events_file"]["row_count"]

    return entry


def build_indexes(data_root: Path):
    """
    Build index.json files from metadata.

    Creates:
      - Per-scope index files (global/index.json, countries/XXX/index.json)
      - Root index.json: Data router pointing to all scopes
    """
    # Group sources by scope
    scopes = {}
    metadata_files = _find_all_metadata_files(data_root)

    for meta_path, rel_path in metadata_files:
        with open(meta_path, encoding="utf-8") as f:
            metadata = json.load(f)

        path_parts = rel_path.split("/")
        if path_parts[0] == "countries" and len(path_parts) >= 2:
            scope = path_parts[1].lower()
        else:
            scope = "global"

        if scope not in scopes:
            scopes[scope] = []
        scopes[scope].append((metadata, rel_path))

    # Build per-scope index files
    for scope, sources in scopes.items():
        if scope == "global":
            index_path = data_root / "global" / "index.json"
        else:
            index_path = data_root / "countries" / scope.upper() / "index.json"

        if not index_path.parent.exists():
            continue

        # Load existing or create new
        if index_path.exists():
            with open(index_path, encoding="utf-8") as f:
                index = json.load(f)
        else:
            index = {
                "_description": f"Index of {scope} datasets",
                "_last_updated": "",
                "datasets": {},
                "categories": {}
            }

        # Update datasets
        for metadata, rel_path in sources:
            source_id = metadata.get("source_id")
            if not source_id:
                continue

            entry = _build_dataset_entry(data_root, metadata, rel_path)
            index["datasets"][source_id] = entry

            category = metadata.get("category", "general")
            if "categories" not in index:
                index["categories"] = {}
            if category not in index["categories"]:
                index["categories"][category] = []
            if source_id not in index["categories"][category]:
                index["categories"][category].append(source_id)

        index["_last_updated"] = date.today().strftime("%Y-%m")

        for cat in index.get("categories", {}):
            index["categories"][cat] = sorted(index["categories"][cat])

        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(index, f, indent=2)

        print(f"  Index saved: {index_path} ({len(index.get('datasets', {}))} datasets)")

    # Build root index.json
    _build_root_index(data_root, scopes)


def _build_root_index(data_root: Path, scopes: dict):
    """Build the root index.json that routes to all data locations."""
    root_index_path = data_root / "index.json"

    # Check for geometry files
    geometry_dir = data_root / "geometry"
    has_admin0_full = (geometry_dir / "admin0" / "full.parquet").exists() if geometry_dir.exists() else False
    has_entities = (geometry_dir / "global_entities.parquet").exists() if geometry_dir.exists() else False
    global_baseline_country_count = (
        len(list(geometry_dir.glob("*.parquet"))) - (1 if has_entities else 0)
        if geometry_dir.exists() else 0
    )

    root_index = {
        "_description": "Data folder routing - which countries have sub-national data folders",
        "_format": "ISO3 -> {has_folder, path, datasets, admin_levels}",
        "_schema_version": "1.1.0",
        "_last_updated": date.today().strftime("%Y-%m"),
    }

    # Global entry
    if scopes.get("global"):
        root_index["_global"] = {
            "_description": "Datasets available at country level (admin_0) for all countries",
            "path": "global",
            "geometry": "geometry/admin0/full.parquet" if has_admin0_full else None,
            "global_entities": "geometry/global_entities.parquet" if has_entities else None,
            "datasets": sorted([
                m.get("source_id") for m, _ in scopes["global"] if m.get("source_id")
            ])
        }

    # Geometry bank
    root_index["_geometry_bank"] = {
        "_description": "Global fallback banks plus country authority geometry",
        "path": "geometry",
        "fallback_pattern": "geometry/{ISO3}.parquet",
        "country_pattern": "geometry/countries/{ISO3}/",
        "catalog": "geometry/geometry_catalog.json",
        "country_count": global_baseline_country_count
    }

    root_index["_layout"] = {
        "country_data": "countries/{ISO3}/",
        "global_data": "global/",
        "country_geometry": "geometry/countries/{ISO3}/",
        "fallback_geometry": "geometry/{ISO3}.parquet",
        "data_catalog": "catalog.json",
        "geometry_catalog": "geometry/geometry_catalog.json",
        "agent_catalog": "agent_catalog/api_catalog.json",
        "ops_catalog": "ops_feed_registry.json",
    }

    # Default entry
    root_index["_default"] = {
        "_description": "Default for countries without dedicated folders",
        "has_folder": False,
        "geometry_outline": "geometry/admin0/full.parquet" if has_admin0_full else None,
        "geometry_global_baseline": (
            "geometry/{ISO3}.parquet" if global_baseline_country_count > 0 else None
        ),
        "admin_levels": [0],
        "datasets": []
    }

    # Country entries
    for scope, sources in scopes.items():
        if scope == "global":
            continue
        code = scope.upper()
        country_dir = data_root / "countries" / code
        if not country_dir.exists():
            continue

        # Check for geometry
        geo_path = data_root / "geometry" / "countries" / code / "geometry.parquet"
        admin_counts = {}
        admin_levels = [0]

        # Detect admin levels from geometry or data
        if geo_path.exists():
            admin_levels = [0, 1, 2]

        root_index[code] = {
            "name": code,
            "has_folder": True,
            "path": f"countries/{code}",
            "geometry": f"geometry/countries/{code}/geometry.parquet" if geo_path.exists() else None,
            "admin_levels": admin_levels,
            "datasets": sorted([
                m.get("source_id") for m, _ in sources if m.get("source_id")
            ])
        }

    with open(root_index_path, "w", encoding="utf-8") as f:
        json.dump(root_index, f, indent=2)

    print(f"  Root index saved: {root_index_path}")


def build_all(data_root: Path):
    """Build catalog.json and all index.json files."""
    print("=" * 60)
    print(f"BUILDING CATALOG AND INDEXES")
    print(f"Data folder: {data_root}")
    print("=" * 60)
    print()

    print("Building catalog.json...")
    build_catalog(data_root)
    print()

    print("Building index.json files...")
    build_indexes(data_root)
    print()

    print("=" * 60)
    print("BUILD COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Build catalog.json and index.json from metadata files in a data folder."
    )
    parser.add_argument(
        "data_folder",
        type=str,
        help="Path to the data folder to scan (e.g. data/ or /path/to/county-map-data)"
    )
    parser.add_argument(
        "--catalog-only",
        action="store_true",
        help="Only build catalog.json"
    )
    parser.add_argument(
        "--indexes-only",
        action="store_true",
        help="Only build index.json files"
    )

    args = parser.parse_args()
    data_root = Path(args.data_folder).resolve()

    if not data_root.exists():
        print(f"Error: folder does not exist: {data_root}")
        exit(1)

    if args.catalog_only:
        build_catalog(data_root)
    elif args.indexes_only:
        build_indexes(data_root)
    else:
        build_all(data_root)
