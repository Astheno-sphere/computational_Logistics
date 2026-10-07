"""Generic scene-raster API endpoints."""

import io
import os
from pathlib import Path

import msgpack
from fastapi import APIRouter, Request, Response

from mapmover.data_loading import get_source_path, load_full_catalog, load_source_metadata
from mapmover.duckdb_helpers import is_cloud_mode
from mapmover.logging_analytics import logger
from mapmover.paths import COUNTRIES_DIR, GEOMETRY_DIR, GLOBAL_DIR
from mapmover.routes.disasters.helpers import msgpack_error, msgpack_response
from mapmover.runtime_config import get_runtime_config
from mapmover.runtime.published_artifacts import read_artifact_bytes

router = APIRouter()

_PHYSICAL_MASKS = {
    "0.25": "land_alpha_0_25deg.msgpack",
    "1": "land_alpha_1_0deg.msgpack",
    "2": "land_alpha_2_0deg.msgpack",
}


def _physical_mask_relative_path(filename: str) -> str:
    return f"geometry/masks/physical_coastline_v1/{filename}"


@router.get("/api/raster/physical-mask/{resolution}")
async def get_physical_mask(resolution: str, req: Request):
    """Serve the version-pinned shared land-alpha clip grid.

    This is intentionally a small, static artifact rather than a source- or
    frame-specific field. It can therefore be cached once and used to clip both
    land and ocean rasters with complementary fractional alpha.
    """
    filename = _PHYSICAL_MASKS.get(str(resolution).strip())
    if filename is None:
        return msgpack_error("Unsupported physical mask resolution", 404)
    relative_path = _physical_mask_relative_path(filename)
    payload = _cloud_object_bytes(relative_path, published=True) if _prefer_published_raster_reads() else None
    if not payload:
        path = GEOMETRY_DIR / "masks" / "physical_coastline_v1" / filename
        payload = path.read_bytes() if path.is_file() else None
    if not payload:
        return msgpack_error("Physical coastline mask is not published", 404)
    etag = f'"physical-coastline-v1-{filename}"'
    if req.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag, "Cache-Control": "public, max-age=31536000, immutable"})
    return Response(
        content=payload,
        media_type="application/msgpack",
        headers={"ETag": etag, "Cache-Control": "public, max-age=31536000, immutable"},
    )


def _require_tifffile():
    """Import tifffile only when a raster endpoint is actually exercised."""
    try:
        import tifffile  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "Raster endpoints require the optional Python package 'tifffile'. "
            "Install county-map/requirements.txt to enable raster scene reads."
        ) from exc
    return tifffile


def _cloud_object_bytes(relative_path: str, *, published: bool = False) -> bytes | None:
    """Fetch one raster object from the active or explicitly published R2 lane."""
    try:
        return read_artifact_bytes(
            relative_path,
            lane="published" if published else "active",
        )
    except Exception as exc:
        logger.warning("Raster cloud read failed for %s: %s", relative_path, exc)
        return None


def _prefer_published_raster_reads() -> bool:
    """Read published raster artifacts when this runtime has R2 configured.

    A local server is frequently used for WIP Ops QA. It must exercise the
    published bundle, not a possibly stale developer data mirror. Local files
    remain an offline fallback if storage is unavailable.
    """
    if is_cloud_mode():
        return True
    cloud_cfg = get_runtime_config().get("cloud", {})
    return bool(
        os.environ.get("S3_BUCKET", "").strip()
        or str(cloud_cfg.get("bucket", "")).strip()
    )


def _normalize_raster_relative_dir(path_value: str) -> str:
    text = str(path_value or "").strip().strip("/")
    return text.removesuffix("/")


def _source_supports_scene_rasters(source_id: str) -> bool:
    metadata = load_source_metadata(source_id) or {}
    raster_products = metadata.get("raster_products") or {}
    scene_rasters = raster_products.get("scene_rasters") or {}
    scenes = scene_rasters.get("scenes") or []
    return isinstance(scenes, list) and bool(scenes)


def _load_scene_catalog(source_id: str) -> dict | None:
    # Local-WIP climate grid: it deliberately stays out of the public catalog
    # until release QA, but uses the same immutable raster endpoint contract.
    if source_id == "era5_land_temperature":
        return {
            "source_id": source_id,
            "display_name": "ERA5 Monthly 2 m Air Temperature",
            "crs": "EPSG:4326",
            "nodata": 255.0,
            "value_unit": "degrees Celsius",
            "relative_dir": "global/climate/land_temperature/rasters",
            "scenes": [
                {"period": "LAND_TEMPERATURE", "file": "LAND_TEMPERATURE.msgpack"},
                {"period": "LAND_TEMPERATURE_LATEST", "file": "LAND_TEMPERATURE_LATEST.msgpack"},
            ],
        }
    # CAMS is a public Ops-only modeled PM2.5 field. Its historical/archive
    # products deliberately remain outside Explore, Research, API, and MCP.
    if source_id == "cams_air_quality":
        return {
            "source_id": source_id,
            "display_name": "CAMS Modeled Surface PM2.5",
            "crs": "EPSG:4326",
            "nodata": 255.0,
            "value_unit": "ug m-3",
            "relative_dir": "global/climate/cams_air_quality/rasters",
            "scenes": [
                {"period": "CAMS_PM25_ANALYSIS_LATEST", "file": "CAMS_PM25_ANALYSIS_LATEST.msgpack"},
            ],
        }
    metadata = load_source_metadata(source_id) or {}
    raster_products = metadata.get("raster_products") or {}
    scene_rasters = raster_products.get("scene_rasters") or {}
    scenes = scene_rasters.get("scenes") or []
    if not isinstance(scenes, list) or not scenes:
        return None
    source_path = get_source_path(source_id)
    relative_dir = _normalize_raster_relative_dir(
        scene_rasters.get("path") or (f"{source_path.relative_to(COUNTRIES_DIR.parent).as_posix()}/rasters" if source_path else "")
    )
    return {
        "source_id": source_id,
        "display_name": str(metadata.get("source_name") or source_id),
        "crs": str(scene_rasters.get("crs") or "EPSG:4326"),
        "nodata": float(scene_rasters.get("nodata") or 0.0),
        "value_unit": str(scene_rasters.get("value_unit") or "Value"),
        "relative_dir": relative_dir,
        "scenes": scenes,
    }


def _find_related_raster_source(source_id: str) -> str | None:
    normalized_source_id = str(source_id or "").strip()
    if not normalized_source_id:
        return None
    if _source_supports_scene_rasters(normalized_source_id):
        return normalized_source_id

    metadata = load_source_metadata(normalized_source_id) or {}
    pack_id = str(metadata.get("pack_id") or "").strip()
    if not pack_id:
        return None

    catalog = load_full_catalog() or {}
    pack_sources = [
        source for source in (catalog.get("sources") or [])
        if str(source.get("pack_id") or "").strip() == pack_id
    ]
    for source in pack_sources:
        candidate = str(source.get("source_id") or "").strip()
        if candidate and candidate != normalized_source_id and _source_supports_scene_rasters(candidate):
            return candidate
    return None


def _raster_dirs_for_source(source_id: str, catalog: dict | None) -> tuple[Path | None, str | None]:
    if source_id == "era5_land_temperature":
        return GLOBAL_DIR / "climate" / "land_temperature" / "rasters", "global/climate/land_temperature/rasters"
    if source_id == "cams_air_quality":
        return GLOBAL_DIR / "climate" / "cams_air_quality" / "rasters", "global/climate/cams_air_quality/rasters"
    source_path = get_source_path(source_id)
    local_dir = source_path / "rasters" if source_path else None
    relative_dir = _normalize_raster_relative_dir((catalog or {}).get("relative_dir"))
    if not relative_dir and source_path is not None:
        try:
            relative_dir = source_path.relative_to(COUNTRIES_DIR.parent).as_posix().rstrip("/") + "/rasters"
        except Exception:
            relative_dir = ""
    return local_dir, relative_dir or None


def _clip_bundle_relative_path(raster_relative_dir: str | None, period: str) -> str | None:
    if not raster_relative_dir:
        return None
    base = raster_relative_dir.strip().rstrip("/")
    if not base:
        return None
    return f"{base}/clip_bundles/{period}.msgpack"


def _load_clip_bundle_bytes(source_id: str, catalog: dict | None, period: str) -> bytes | None:
    raster_dir, raster_relative_dir = _raster_dirs_for_source(source_id, catalog)
    relative_path = _clip_bundle_relative_path(raster_relative_dir, period)
    if _prefer_published_raster_reads() and relative_path:
        published_bundle = _cloud_object_bytes(relative_path, published=True)
        if published_bundle:
            return published_bundle
    if raster_dir is None:
        return None
    bundle_path = raster_dir / "clip_bundles" / f"{period}.msgpack"
    if not bundle_path.exists():
        return None
    return bundle_path.read_bytes()


def _clip_bundle_etag_cheap(source_id: str, catalog: dict | None, period: str) -> str | None:
    """A cheap ETag (no body read) for the local bundle file via stat. In cloud
    mode we fall back to a content hash after the read."""
    if _prefer_published_raster_reads():
        return None
    raster_dir, _ = _raster_dirs_for_source(source_id, catalog)
    if raster_dir is None:
        return None
    bundle_path = raster_dir / "clip_bundles" / f"{period}.msgpack"
    if not bundle_path.exists():
        return None
    st = bundle_path.stat()
    return f'"{int(st.st_mtime)}-{st.st_size}"'


def _load_clip_bundle_payload(source_id: str, catalog: dict | None, period: str) -> dict | None:
    raw = _load_clip_bundle_bytes(source_id, catalog, period)
    if not raw:
        return None
    try:
        payload = msgpack.unpackb(raw, raw=False)
    except Exception as exc:
        logger.warning(f"Could not decode raster clip bundle for {source_id} {period}: {exc}")
        return None
    return payload if isinstance(payload, dict) else None


async def _decode_msgpack_request(req: Request) -> dict:
    body_bytes = await req.body()
    return msgpack.unpackb(body_bytes, raw=False)


@router.get("/api/raster/resolve/{source_id}")
async def resolve_raster_source(source_id: str):
    """Resolve a source or its pack sibling to the raster-capable source id."""
    resolved_source_id = _find_related_raster_source(source_id)
    if not resolved_source_id:
        return msgpack_error(f"No raster-capable source found for {source_id}", 404)
    catalog = _load_scene_catalog(resolved_source_id)
    if catalog is None:
        return msgpack_error(f"Raster scene catalog not found for {resolved_source_id}", 404)
    return msgpack_response({
        "requested_source_id": source_id,
        "source_id": resolved_source_id,
        "display_name": catalog.get("display_name") or resolved_source_id,
        "scene_count": len(catalog.get("scenes") or []),
    })


@router.get("/api/raster/{source_id}/scenes")
async def get_raster_scenes(source_id: str):
    """Return source-driven scene-raster metadata from the source metadata contract."""
    catalog = _load_scene_catalog(source_id)
    if catalog is None:
        return msgpack_error(f"Raster scene catalog not found for {source_id}", 404)
    return msgpack_response(catalog)


@router.get("/api/raster/{source_id}/{period}")
async def get_raster_scene(source_id: str, period: str):
    """Return pixel data for one published scene raster."""
    import numpy as np

    catalog = _load_scene_catalog(source_id)
    if catalog is None:
        return msgpack_error(f"Raster scene catalog not found for {source_id}", 404)

    scene = next((s for s in catalog.get("scenes", []) if s["period"] == period), None)
    if scene is None:
        return msgpack_error(f"Unknown period: {period}", 404)

    bounds = scene.get("bounds")
    if not bounds:
        return msgpack_error(f"No bounds in metadata for period: {period}", 500)

    raster_dir, raster_relative_dir = _raster_dirs_for_source(source_id, catalog)

    try:
        tifffile = _require_tifffile()
        if is_cloud_mode():
            raw_tif = _cloud_object_bytes(f"{raster_relative_dir}/{scene['file']}")
            if raw_tif is None:
                return msgpack_error(f"Raster file not found for period: {period}", 404)
            data = tifffile.imread(io.BytesIO(raw_tif))
        else:
            tif_path = raster_dir / scene["file"]
            if not tif_path.exists():
                logger.warning(f"Raster file missing for {source_id}: {tif_path}")
                return msgpack_error(f"Raster file not found for period: {period}", 404)
            data = tifffile.imread(str(tif_path))

        return msgpack_response({
            "source_id": source_id,
            "pixels": data.astype(np.float32).tobytes(),
            "width": int(scene["width"]),
            "height": int(scene["height"]),
            "bounds": {
                "west": float(bounds["west"]),
                "south": float(bounds["south"]),
                "east": float(bounds["east"]),
                "north": float(bounds["north"]),
            },
            "nodata": 0.0,
            "period": period,
            "year": int(scene["year"]),
        })

    except Exception as exc:
        logger.error(f"Raster read error for {source_id} period {period}: {exc}")
        return msgpack_error("Failed to read raster data", 500)


@router.get("/api/raster/{source_id}/clip-bundle/{period}")
async def get_raster_clip_bundle(source_id: str, period: str, req: Request):
    """Return a prebuilt msgpack clip bundle for one scene period.

    These bundles are large (tens to hundreds of MB) and immutable until a
    rebuild/republish, so they are browser-cacheable with revalidation: we send
    an ETag and `Cache-Control: no-cache`, and answer a matching `If-None-Match`
    with 304 so the browser never re-downloads an unchanged bundle (e.g. after a
    server reset). See CACHING.md (Layer 0 artifact, browser-cached + revalidated)."""
    import hashlib

    catalog = _load_scene_catalog(source_id)
    if catalog is None:
        return msgpack_error(f"Raster scene catalog not found for {source_id}", 404)

    scene = next((s for s in catalog.get("scenes", []) if s["period"] == period), None)
    if scene is None:
        return msgpack_error(f"Unknown period: {period}", 404)

    inm = req.headers.get("if-none-match")

    # Cheap revalidation: if we can ETag from the local file stat, answer 304
    # without ever loading the bytes.
    etag = _clip_bundle_etag_cheap(source_id, catalog, period)
    if etag and inm and inm == etag:
        return Response(status_code=304, headers={"ETag": etag, "Cache-Control": "no-cache"})

    raw_bundle = _load_clip_bundle_bytes(source_id, catalog, period)
    if not raw_bundle:
        return msgpack_error(f"Raster clip bundle not found for period: {period}", 404)

    if not etag:
        etag = '"' + hashlib.md5(raw_bundle).hexdigest() + '"'
        if inm and inm == etag:
            return Response(status_code=304, headers={"ETag": etag, "Cache-Control": "no-cache"})

    return Response(
        content=raw_bundle,
        media_type="application/msgpack",
        headers={"ETag": etag, "Cache-Control": "no-cache"},
    )


@router.post("/api/raster/{source_id}/clips")
async def get_raster_clips(source_id: str, req: Request):
    """Return loc_id-specific raster clips for a given source and scene period."""
    try:
        body = await _decode_msgpack_request(req)
        period = str(body.get("period") or "").strip()
        loc_ids = [str(value).strip() for value in (body.get("loc_ids") or []) if str(value).strip()]
        if not period:
            return msgpack_error("No period provided", 400)
        if not loc_ids:
            return msgpack_error("No loc_ids provided", 400)

        catalog = _load_scene_catalog(source_id)
        if catalog is None:
            return msgpack_error(f"Raster scene catalog not found for {source_id}", 404)
        scene = next((s for s in catalog.get("scenes", []) if s["period"] == period), None)
        if scene is None:
            return msgpack_error(f"Unknown period: {period}", 404)

        bundle_payload = _load_clip_bundle_payload(source_id, catalog, period)
        if not bundle_payload:
            return msgpack_error(
                f"Raster clip bundle not found for period: {period}. "
                "This runtime now depends on published clip bundles rather than legacy per-clip TIFFs.",
                404,
            )

        clips_by_loc_id = bundle_payload.get("clips_by_loc_id") or {}
        clips = []
        for loc_id in loc_ids[:50]:
            clip = clips_by_loc_id.get(loc_id)
            if not isinstance(clip, dict):
                continue

            clips.append({
                "loc_id": loc_id,
                "level": str(clip.get("level") or ""),
                "period": period,
                "pixels": clip.get("pixels") or b"",
                "width": int(clip.get("width") or 0),
                "height": int(clip.get("height") or 0),
                "bounds": clip.get("bounds") or {},
                "nodata": float(clip.get("nodata") or 0.0),
            })

        return msgpack_response({
            "source_id": source_id,
            "period": period,
            "year": int(bundle_payload.get("year") or scene["year"]),
            "clip_count": len(clips),
            "clips": clips,
        })
    except Exception as exc:
        logger.error(f"Raster clip read error for {source_id}: {exc}")
        return msgpack_error("Failed to read raster clips", 500)
