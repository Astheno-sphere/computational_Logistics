"""Bounded startup warm set for high-frequency identity conversion."""
from __future__ import annotations

import logging
from typing import Any

from ..foundation_helpers import load_country_crosswalk, load_reference_dict
from .admin_spine_query import prewarm_shallow_identity_index
from .global_admin0_query import load_global_admin0_identities


logger = logging.getLogger(__name__)


def prewarm_reference_identities() -> dict[str, Any]:
    """Warm small country helpers plus the current USA conversion spine.

    This deliberately contains no polygons. Additional countries belong here
    only after observed conversion traffic justifies making their identity
    indexes part of every hosted process's resident set.
    """
    iso_codes = load_reference_dict("iso_codes.json") or {}
    country_aliases = load_reference_dict("country_aliases.json") or {}
    codes = list(dict.fromkeys(
        str(value).strip().upper()
        for section in ("common_countries", "commonly_missing")
        for value in ((iso_codes.get(section) or {}).get("codes") or [])
        if str(value).strip()
    ))
    admin0 = load_global_admin0_identities(codes) or {}
    usa_crosswalk = load_country_crosswalk("USA") or {}
    usa_rows = prewarm_shallow_identity_index("USA", maximum_level=2)
    result = {
        "iso_codes": len(codes),
        "country_aliases": len(country_aliases.get("aliases") or {}),
        "global_admin0_identities": len(admin0),
        "usa_crosswalk_sections": len(usa_crosswalk),
        "usa_admin0_2_identities": usa_rows,
    }
    logger.info("Reference identity pre-warmer complete: %s", result)
    return result
