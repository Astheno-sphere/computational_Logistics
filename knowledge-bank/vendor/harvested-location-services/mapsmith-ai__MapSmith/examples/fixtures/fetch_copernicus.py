"""Rebuild the two Copernicus clips the 04 notebook reads, from the public archives.

    python fetch_copernicus.py

The notebook needs no network: both clips are committed next to this file. This
script is how they were made, so that where a number in the notebook comes from
can be checked instead of believed. It reads two windows over HTTPS (GDAL's
/vsicurl/, anonymous) and writes:

* ``monte_baldo_dem.tif`` -- Copernicus DEM GLO-30, a 252 x 180 window of tile
  N45 E010, as published: EPSG:4326, 1 arc-second, float32, heights above the
  EGM2008 geoid, point-registered (``AREA_OR_POINT=Point``, which GDAL already
  turned into an origin half a cell up and left), with the product's invalid
  value -32767 declared as nodata.
* ``monte_baldo_s2.tif`` -- Sentinel-2 L2A item ``S2C_32TPR_20250813_0_L2A``
  (13 August 2025, 0.54% cloud), bands B04 (red) and B08 (near infrared) at
  10 m in UTM 32N, uint16, nodata 0.

The one decision this script makes, and the reason it is written down: the
STAC item declares ``scale 0.0001, offset -0.1`` for both bands, and the COGs
themselves declare neither. The offset is ALREADY in these pixels -- deep water
in Lake Garda reads 276-303 in the near infrared, which is a reflectance of
0.028-0.030 with the scale alone and -0.07 with the offset applied again, and a
negative reflectance does not exist. So the clip declares the scale and an
offset of 0, measured on this item and on nothing else: another item or another
archive may differ, which is the point of measuring.

Attribution and licences: see COPERNICUS-NOTICE.md in this folder.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds

HERE = Path(__file__).resolve().parent
DEM_URL = (
    "https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N45_00_E010_00_DEM/"
    "Copernicus_DSM_COG_10_N45_00_E010_00_DEM.tif"
)
ITEM = "S2C_32TPR_20250813_0_L2A"
S2_URL = (
    "https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/32/T/PR/2025/8/"
    f"{ITEM}/{{band}}.tif"
)
#: Monte Baldo's western flank, from Lake Garda at Malcesine to the ridge.
BOX = (10.80, 45.72, 10.87, 45.77)
WATER = (10.775, 45.76)  # deep water off Malcesine, outside the clip, for the offset check


def _window(src, bounds):
    left, bottom, right, top = transform_bounds("EPSG:4326", src.crs, *bounds)
    return from_bounds(left, bottom, right, top, transform=src.transform).round_offsets().round_lengths()


def _profile(src, window, count):
    profile = src.profile.copy()
    for key in ("blockxsize", "blockysize", "photometric"):
        profile.pop(key, None)
    profile.update(
        driver="GTiff", tiled=False, compress="deflate", count=count,
        width=int(window.width), height=int(window.height),
        transform=src.window_transform(window),
    )
    return profile


def dem() -> Path:
    out = HERE / "monte_baldo_dem.tif"
    with rasterio.open(DEM_URL) as src:
        window = _window(src, BOX)
        data = src.read(1, window=window)
        profile = _profile(src, window, 1)
        tags = src.tags()
    # The COG declares no nodata; the product metadata beside it declares
    # -32767 as the invalid-pixel value, and this window has none. Declared
    # here so that a reprojection's fill is nodata and not a height of 0 m,
    # which is what the 04 notebook got first -- the reprojection's own
    # `fill_is_distinguishable` check said so.
    assert not (data == -32767).any()
    profile["nodata"] = -32767.0
    with rasterio.open(out, "w", **profile) as dst:
        dst.update_tags(**tags, SOURCE=DEM_URL)
        dst.write(data, 1)
    return out


def sentinel() -> Path:
    out = HERE / "monte_baldo_s2.tif"
    bands = []
    for band in ("B04", "B08"):
        with rasterio.open(S2_URL.format(band=band)) as src:
            window = _window(src, BOX)
            bands.append(src.read(1, window=window))
            if band == "B08":
                x, y = rasterio.warp.transform("EPSG:4326", src.crs, [WATER[0]], [WATER[1]])
                row, col = src.index(x[0], y[0])
                water = int(np.median(src.read(1, window=((row - 2, row + 3), (col - 2, col + 3)))))
            profile = _profile(src, window, 2)
            tags = src.tags()
    # The measurement the decision rests on, re-made every time the clip is.
    assert water * 0.0001 - 0.1 < 0 < water * 0.0001, (
        f"deep-water NIR is {water}: the offset question has a different answer "
        "for this item than the one written above -- re-read it before shipping"
    )
    with rasterio.open(out, "w", **profile) as dst:
        dst.update_tags(**tags, SOURCE_ITEM=ITEM, DEEP_WATER_NIR_DN=str(water))
        dst.scales = (0.0001, 0.0001)
        dst.offsets = (0.0, 0.0)
        dst.descriptions = ("B04 red", "B08 near infrared")
        dst.write(np.stack(bands))
    return out


if __name__ == "__main__":
    for path in (dem(), sentinel()):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        print(f"{path.name}: {path.stat().st_size} bytes, sha256 {digest}")
