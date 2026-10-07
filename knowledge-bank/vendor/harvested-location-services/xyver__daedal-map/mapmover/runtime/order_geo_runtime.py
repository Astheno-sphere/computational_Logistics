"""Shared order-execution geography helpers."""

from __future__ import annotations

US_REGIONAL_GROUPS = {
    "usa west": {"USA-AZ", "USA-CA", "USA-CO", "USA-ID", "USA-MT", "USA-NM", "USA-NV", "USA-OR", "USA-UT", "USA-WA", "USA-WY"},
    "western us": {"USA-AZ", "USA-CA", "USA-CO", "USA-ID", "USA-MT", "USA-NM", "USA-NV", "USA-OR", "USA-UT", "USA-WA", "USA-WY"},
    "western u.s.": {"USA-AZ", "USA-CA", "USA-CO", "USA-ID", "USA-MT", "USA-NM", "USA-NV", "USA-OR", "USA-UT", "USA-WA", "USA-WY"},
    "western united states": {"USA-AZ", "USA-CA", "USA-CO", "USA-ID", "USA-MT", "USA-NM", "USA-NV", "USA-OR", "USA-UT", "USA-WA", "USA-WY"},
}


def expand_order_region(
    region: str,
    *,
    resolve_country_subdivision_slug_loc_id_func,
    load_conversions_func,
    load_iso_codes_func,
    load_usa_admin_func,
    prefer_water_body: bool = False,
):
    from mapmover.runtime.region_expansion import expand_region as expand_region_impl

    return expand_region_impl(
        region,
        resolve_country_subdivision_slug_loc_id_func=resolve_country_subdivision_slug_loc_id_func,
        regional_groups=US_REGIONAL_GROUPS,
        load_conversions_func=load_conversions_func,
        load_iso_codes_func=load_iso_codes_func,
        load_usa_admin_func=load_usa_admin_func,
        prefer_water_body=prefer_water_body,
    )
