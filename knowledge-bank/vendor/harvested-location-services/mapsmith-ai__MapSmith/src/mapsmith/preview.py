"""Preview payloads for the in-chat map panel (MCP Apps).

Turns MapSmith outputs into something a map UI can render: vector layers as
capped, simplified GeoJSON in EPSG:4326; rasters as small grayscale PNG
overlays with approximate 4326 bounds; plus a compact provenance summary per
layer so the panel can show WHAT produced each layer and whether it verified.

Previews are read-only and lossy by design (simplified geometry, capped
feature counts, downsampled rasters): the dataset of record stays on disk with
its manifest. Nothing here feeds analysis — invariant 1 is untouched.
"""

from __future__ import annotations

import base64
import json
import struct
import zlib
from pathlib import Path
from typing import Any

from . import readers, verify

MAX_FEATURES = 2000
MAX_RASTER_PX = 512
_GEOGRAPHIC_PREVIEW_CRS = "EPSG:4326"  # what web maps speak


# One label function and one reader for the whole package: a preview that
# disagreed with the manifest about the same file would be worse than no
# preview, and #28 was exactly the read path here drifting from the others.
_crs_label = verify.crs_label
_read_vector_capped = readers.read_vector_capped


def provenance_summary(path: str) -> dict[str, Any] | None:
    """Compact manifest summary for the panel; None when no manifest exists."""
    manifest_path = Path(f"{path}.provenance.json")
    if not manifest_path.exists():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    checks = manifest.get("verification")
    if not isinstance(checks, list):
        checks = []
    critical = [c for c in checks if c.get("critical", True)]
    # Three states, because two would lie. "All critical checks passed" is
    # vacuously true when no critical check ran — which is exactly the run_sql
    # case (SQL is opaque, so its only check is non-critical), and it would put
    # a green tick on an output whose single check FAILED and whose manifest
    # declares no inputs at all. That is the one place where "geometry never
    # comes from the model" is not structurally guaranteed, so the panel must
    # not render it like a verified buffer.
    if any(c.get("passed") is not True for c in critical):
        status = "failed"
    elif critical:
        status = "verified"
    else:
        status = "unchecked"
    return {
        "operation": manifest.get("operation"),
        "engine": (manifest.get("engine") or {}).get("name"),
        "status": status,
        "verified": status == "verified",
        "checks_total": len(checks),
        "checks_critical": len(critical),
        # an empty input list means the lineage could not be determined
        # statically (run_sql), not that there were no inputs
        "inputs_recorded": bool(manifest.get("inputs")),
        "repairs": len(manifest.get("repairs") or []),
        "crs_reason": (manifest.get("crs_decisions") or {}).get("reason"),
        "finished_at": manifest.get("finished_at"),
    }


def vector_preview(path: str, max_features: int = MAX_FEATURES) -> dict[str, Any]:
    """Vector layer as simplified GeoJSON in EPSG:4326, capped at max_features.

    `bounds` always covers the FULL dataset (from layer metadata), so a
    truncated preview never lies about the extent it stands for.
    """
    gdf, total, native_bounds = _read_vector_capped(path, max_features)
    if gdf.crs is None:
        raise ValueError(readers.no_crs_message(
            gdf, f"{path} has no CRS — cannot place it on a map. Assign a CRS first."
        ))
    if total == 0 or native_bounds is None:
        raise ValueError(f"{path} has no features — nothing to preview.")
    truncated = total > max_features
    original_crs = _crs_label(gdf.crs)

    from pyproj import Transformer

    bounds = Transformer.from_crs(
        gdf.crs, _GEOGRAPHIC_PREVIEW_CRS, always_xy=True
    ).transform_bounds(*native_bounds)
    gdf = gdf.to_crs(_GEOGRAPHIC_PREVIEW_CRS)
    # tolerance scaled to the full extent: ~1/1000 of the diagonal keeps shapes
    # recognizable while cutting payload size drastically on dense polygons.
    minx, miny, maxx, maxy = bounds
    diagonal = ((maxx - minx) ** 2 + (maxy - miny) ** 2) ** 0.5
    if diagonal > 0:
        gdf = gdf.assign(geometry=gdf.geometry.simplify(diagonal / 1000))
    # datetime/timedelta columns are not JSON serializable: stringify them
    geometry_name = gdf.geometry.name
    for col in gdf.columns:
        if col != geometry_name and gdf[col].dtype.kind in "Mm":
            gdf[col] = gdf[col].astype(str)
    try:
        geojson = json.loads(gdf.to_json())
    except TypeError:  # exotic column types: stringify everything non-geometry
        for col in gdf.columns:
            if col != geometry_name:
                gdf[col] = gdf[col].astype(str)
        geojson = json.loads(gdf.to_json())
    return {
        "kind": "vector",
        "path": str(path),
        "name": Path(path).stem,
        "geojson": geojson,
        "feature_count": total,
        "truncated": truncated,
        "crs_original": original_crs,
        "bounds": [float(v) for v in bounds],
        "provenance": provenance_summary(path),
    }


def _png_gray_alpha(rows: list[bytes], width: int, height: int) -> bytes:
    """Minimal deterministic 8-bit grayscale+alpha PNG encoder (stdlib only).

    Each row is 2*width bytes (gray, alpha interleaved). Alpha lets nodata be
    transparent instead of covering the layers underneath in black.
    """

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + tag
            + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", width, height, 8, 4, 0, 0, 0)  # color type 4
    raw = b"".join(b"\x00" + row for row in rows)  # filter type 0 per scanline
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def raster_preview(path: str, max_px: int = MAX_RASTER_PX) -> dict[str, Any]:
    """Raster as a small grayscale PNG data URI with approximate 4326 bounds.

    Requires the [raster] extra. Pixels are min-max stretched to 8 bit and the
    native grid is draped onto reprojected bounds — good enough for a preview,
    never for analysis.
    """
    try:
        import numpy as np
        import rasterio
        from rasterio.warp import transform_bounds
    except ImportError as exc:
        raise ImportError(
            "raster previews require the raster extra: pip install mapsmith[raster]"
        ) from exc

    with rasterio.open(path) as ds:
        if ds.crs is None:
            raise ValueError(
                f"{path} has no CRS — cannot place it on a map. Assign a CRS first."
            )
        scale = max(1, max(ds.height, ds.width) // max_px)
        out_h, out_w = max(1, ds.height // scale), max(1, ds.width // scale)
        data = ds.read(1, out_shape=(out_h, out_w)).astype("float64")
        nodata = ds.nodata
        bounds = transform_bounds(ds.crs, _GEOGRAPHIC_PREVIEW_CRS, *ds.bounds)
        crs_original = _crs_label(ds.crs)

    # NaN pixels are invalid even when a non-NaN nodata is declared (mixed rasters)
    if nodata is not None and not np.isnan(nodata):
        mask = (data != nodata) & ~np.isnan(data)
    else:
        mask = ~np.isnan(data)
    valid = data[mask]
    lo, hi = (float(valid.min()), float(valid.max())) if valid.size else (0.0, 0.0)
    stretched = np.zeros(data.shape, dtype="uint8")
    if hi > lo:
        stretched[mask] = ((data[mask] - lo) / (hi - lo) * 255).astype("uint8")
    elif valid.size:
        stretched[mask] = 128  # constant raster: mid-gray beats all-black
    alpha = np.where(mask, 255, 0).astype("uint8")  # nodata -> transparent
    interleaved = np.dstack([stretched, alpha])
    png = _png_gray_alpha(
        [interleaved[r].tobytes() for r in range(interleaved.shape[0])],
        stretched.shape[1],
        stretched.shape[0],
    )
    return {
        "kind": "raster",
        "path": str(path),
        "name": Path(path).stem,
        "png_data_uri": "data:image/png;base64," + base64.b64encode(png).decode(),
        "bounds": [float(v) for v in bounds],
        "value_range": [lo, hi],
        "crs_original": crs_original,
        "width": stretched.shape[1],
        "height": stretched.shape[0],
        "provenance": provenance_summary(path),
    }


MAX_PAYLOAD_CHARS = 120_000  # Claude clients cap tool results around ~150k chars


def _build_preview(paths: list[str], max_features: int, max_px: int) -> dict[str, Any]:
    layers = []
    for path in paths:
        lower = str(path).lower()
        if lower.endswith((".tif", ".tiff")):
            layers.append(raster_preview(path, max_px=max_px))
        else:
            layers.append(vector_preview(path, max_features=max_features))
    xs: list[float] = []
    ys: list[float] = []
    for layer in layers:
        minx, miny, maxx, maxy = layer["bounds"]
        xs += [minx, maxx]
        ys += [miny, maxy]
    return {
        "layers": layers,
        "bounds": [min(xs), min(ys), max(xs), max(ys)],
        "crs": _GEOGRAPHIC_PREVIEW_CRS,
    }


def map_preview(
    paths: list[str],
    max_features: int = MAX_FEATURES,
    max_payload_chars: int = MAX_PAYLOAD_CHARS,
) -> dict[str, Any]:
    """Preview payload for a set of layers, sized to fit client tool-result caps.

    When the serialized payload exceeds the budget, feature caps and raster
    resolution are halved (deterministically) until it fits or hits the floor.
    """
    if not paths:
        raise ValueError("pass at least one dataset path to preview")
    features_cap = max_features
    features_floor = min(50, max_features)  # never raise a cap the caller lowered
    raster_px = MAX_RASTER_PX
    while True:
        payload = _build_preview(paths, features_cap, raster_px)
        size = len(json.dumps(payload))
        at_floor = features_cap <= features_floor and raster_px <= 128
        if size <= max_payload_chars or at_floor:
            payload["payload_chars"] = size
            if size > max_payload_chars:
                payload["oversize"] = True  # floor reached: client may still truncate
            return payload
        features_cap = max(features_floor, features_cap // 2)
        raster_px = max(128, raster_px // 2)
