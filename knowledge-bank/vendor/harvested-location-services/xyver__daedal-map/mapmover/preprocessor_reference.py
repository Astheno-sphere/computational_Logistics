"""Reference lookup helpers extracted from preprocessor.py."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, Optional


def lookup_country_specific_data(
    ref_type: str,
    iso3: str,
    country_name: str,
    *,
    reference_dir: Path,
    load_reference_file: Callable[[Path], Optional[dict]],
) -> Optional[dict]:
    """Look up specific country data from reference files."""
    if ref_type == "currency":
        ref_path = reference_dir / "currencies_scraped.json"
        if ref_path.exists():
            data = load_reference_file(ref_path) or {}
            currencies = data.get("currencies", {})
            if iso3 in currencies:
                currency = currencies[iso3]
                return {
                    "country": country_name,
                    "iso3": iso3,
                    "currency_code": currency.get("code"),
                    "currency_name": currency.get("name"),
                    "formatted": f"{country_name} uses {currency.get('name')} ({currency.get('code')})",
                }

    elif ref_type == "language":
        ref_path = reference_dir / "languages_scraped.json"
        if ref_path.exists():
            data = load_reference_file(ref_path) or {}
            languages = data.get("languages", {})
            if iso3 in languages:
                lang_data = languages[iso3]
                official = lang_data.get("official", [])
                all_langs = lang_data.get("languages", [])
                return {
                    "country": country_name,
                    "iso3": iso3,
                    "official_languages": official,
                    "all_languages": all_langs,
                    "formatted": (
                        f"{country_name}: Official language(s): {', '.join(official) if official else 'N/A'}. "
                        f"All languages: {', '.join(all_langs[:5]) if all_langs else 'N/A'}"
                    ),
                }

    elif ref_type == "timezone":
        ref_path = reference_dir / "timezones_scraped.json"
        if ref_path.exists():
            data = load_reference_file(ref_path) or {}
            timezones = data.get("timezones", {})
            if iso3 in timezones:
                tz_data = timezones[iso3]
                return {
                    "country": country_name,
                    "iso3": iso3,
                    "utc_offset": tz_data.get("utc_offset"),
                    "has_dst": tz_data.get("has_dst"),
                    "num_timezones": tz_data.get("num_timezones"),
                    "formatted": (
                        f"{country_name}: {tz_data.get('utc_offset')}"
                        + (f" (DST observed)" if tz_data.get("has_dst") else "")
                        + (
                            f" ({tz_data.get('num_timezones')} time zones)"
                            if tz_data.get("num_timezones", 1) > 1
                            else ""
                        )
                    ),
                }

    elif ref_type == "capital":
        ref_path = reference_dir / "country_metadata.json"
        if ref_path.exists():
            data = load_reference_file(ref_path) or {}
            capitals = data.get("capitals", {})
            if iso3 in capitals:
                capital = capitals[iso3]
                return {
                    "country": country_name,
                    "iso3": iso3,
                    "capital": capital,
                    "formatted": f"The capital of {country_name} is {capital}" if capital else f"Capital not found for {country_name}",
                }

    return None


def detect_reference_lookup(
    query: str,
    *,
    reference_dir: Path,
    load_catalog: Callable[[], Optional[dict]],
    get_source_path: Callable[[str], Optional[Path]],
    load_reference_file: Callable[[Path], Optional[dict]],
    extract_country_from_query: Callable[[str], dict],
) -> Optional[dict]:
    """
    Detect if query is asking for reference information.

    Returns dict with reference file path, type, and specific country data if found.
    """
    query_lower = query.lower()

    currency_analytics_terms = [
        "against usd",
        "vs usd",
        "drop",
        "depreciat",
        "appreciat",
        "volatility",
        "single year",
        "over the last",
        "trend",
        "time series",
        "change",
        "percent",
        "over time",
        "since ",
        "between ",
        "compare",
    ]
    is_currency_analytics = (
        "currency" in query_lower or "fx" in query_lower or "exchange rate" in query_lower
    ) and any(term in query_lower for term in currency_analytics_terms)

    help_keywords = [
        "how do you work",
        "how does this work",
        "what can you do",
        "what can i do",
        "what can i ask",
        "how do i use",
        "how to use",
        "what is this",
        "what are you",
        "tell me about yourself",
        "help me",
        "what do you do",
        "how do i ask",
        "what questions can i",
    ]
    is_short_help = query_lower.strip() in ["help", "?", "help me", "how"]
    if is_short_help or any(kw in query_lower for kw in help_keywords):
        ref_path = reference_dir / "system_help.json"
        if ref_path.exists():
            return {
                "type": "system_help",
                "file": str(ref_path),
                "content": load_reference_file(ref_path),
            }

    sdg_match = re.search(r"sdg\s*(\d+)|goal\s*(\d+)|sustainable development goal\s*(\d+)", query_lower)
    if sdg_match:
        num = sdg_match.group(1) or sdg_match.group(2) or sdg_match.group(3)
        goal_num = int(num)
        goal_tag = f"goal{goal_num}"
        catalog = load_catalog()
        if catalog:
            for source in catalog.get("sources", []):
                if goal_tag in source.get("topic_tags", []):
                    source_path = get_source_path(source.get("source_id"))
                    if source_path:
                        ref_path = source_path / "reference.json"
                        if ref_path.exists():
                            return {
                                "type": "sdg",
                                "sdg_number": goal_num,
                                "file": str(ref_path),
                                "content": load_reference_file(ref_path),
                            }
                    break

    iso3 = None
    country_name = None

    def ensure_country_context() -> tuple[str | None, str | None]:
        nonlocal iso3, country_name
        if iso3 is not None or country_name is not None:
            return iso3, country_name
        country_result = extract_country_from_query(query)
        if country_result.get("match"):
            matched_term, resolved_iso3, _is_subregion = country_result["match"]
            iso_data = load_reference_file(reference_dir / "iso_codes.json") or {}
            country_name = iso_data.get("iso3_to_name", {}).get(resolved_iso3, matched_term.title())
            iso3 = resolved_iso3
        return iso3, country_name

    if any(kw in query_lower for kw in ["capital of", "capital city"]):
        result = {"type": "capital", "file": str(reference_dir / "country_metadata.json")}
        iso3, country_name = ensure_country_context()
        if iso3:
            specific = lookup_country_specific_data(
                "capital",
                iso3,
                country_name,
                reference_dir=reference_dir,
                load_reference_file=load_reference_file,
            )
            if specific:
                result["country_data"] = specific
        return result

    if any(kw in query_lower for kw in ["currency", "money in", "monetary unit"]) and not is_currency_analytics:
        result = {"type": "currency", "file": str(reference_dir / "currencies_scraped.json")}
        iso3, country_name = ensure_country_context()
        if iso3:
            specific = lookup_country_specific_data(
                "currency",
                iso3,
                country_name,
                reference_dir=reference_dir,
                load_reference_file=load_reference_file,
            )
            if specific:
                result["country_data"] = specific
        return result

    if any(kw in query_lower for kw in ["language", "speak", "spoken", "official language"]):
        result = {"type": "language", "file": str(reference_dir / "languages_scraped.json")}
        iso3, country_name = ensure_country_context()
        if iso3:
            specific = lookup_country_specific_data(
                "language",
                iso3,
                country_name,
                reference_dir=reference_dir,
                load_reference_file=load_reference_file,
            )
            if specific:
                result["country_data"] = specific
        return result

    if any(kw in query_lower for kw in ["timezone", "time zone", "what time"]):
        result = {"type": "timezone", "file": str(reference_dir / "timezones_scraped.json")}
        iso3, country_name = ensure_country_context()
        if iso3:
            specific = lookup_country_specific_data(
                "timezone",
                iso3,
                country_name,
                reference_dir=reference_dir,
                load_reference_file=load_reference_file,
            )
            if specific:
                result["country_data"] = specific
        return result

    background_keywords = ["background", "history of", "tell me about", "overview of", "about the country"]
    if any(kw in query_lower for kw in background_keywords):
        iso3, country_name = ensure_country_context()
    if iso3 and any(kw in query_lower for kw in background_keywords):
        ref_path = reference_dir / "world_factbook_text.json"
        if ref_path.exists():
            data = load_reference_file(ref_path) or {}
            countries = data.get("countries", {})
            if iso3 in countries:
                country_data = countries[iso3]
                background = country_data.get("background", "")
                if background:
                    summary = background[:800] + "..." if len(background) > 800 else background
                    return {
                        "type": "country_info",
                        "file": str(ref_path),
                        "country_data": {
                            "country": country_name,
                            "iso3": iso3,
                            "background": background,
                            "formatted": f"{country_name} Background: {summary}",
                        },
                    }

    economy_keywords = ["economy", "economic", "industries", "gdp"]
    if any(kw in query_lower for kw in economy_keywords):
        iso3, country_name = ensure_country_context()
    if iso3 and any(kw in query_lower for kw in economy_keywords):
        ref_path = reference_dir / "world_factbook_text.json"
        if ref_path.exists():
            data = load_reference_file(ref_path) or {}
            countries = data.get("countries", {})
            if iso3 in countries:
                country_data = countries[iso3]
                econ = country_data.get("economic_overview", "")
                industries = country_data.get("industries", "")
                if econ or industries:
                    parts = []
                    if econ:
                        parts.append(f"Economic Overview: {econ[:400]}")
                    if industries:
                        parts.append(f"Industries: {industries}")
                    return {
                        "type": "economy_info",
                        "file": str(ref_path),
                        "country_data": {
                            "country": country_name,
                            "iso3": iso3,
                            "economic_overview": econ,
                            "industries": industries,
                            "formatted": f"{country_name} - " + "; ".join(parts),
                        },
                    }

    trade_keywords = [
        "trade partner",
        "trading partner",
        "export partner",
        "import partner",
        "exports of",
        "imports of",
        "main export",
        "main import",
        "top export",
        "top import",
        "trade with",
        "trades with",
        "trading with",
        "who export",
        "who import",
    ]
    if any(kw in query_lower for kw in trade_keywords):
        iso3, country_name = ensure_country_context()
    if iso3 and any(kw in query_lower for kw in trade_keywords):
        ref_path = reference_dir / "world_factbook_text.json"
        if ref_path.exists():
            data = load_reference_file(ref_path) or {}
            countries = data.get("countries", {})
            if iso3 in countries:
                country_data = countries[iso3]
                exports_commodities = country_data.get("exports_commodities", "")
                exports_partners = country_data.get("exports_partners", "")
                imports_commodities = country_data.get("imports_commodities", "")
                imports_partners = country_data.get("imports_partners", "")
                if exports_partners or imports_partners or exports_commodities or imports_commodities:
                    parts = []
                    if exports_partners:
                        parts.append(f"Export partners: {exports_partners}")
                    if exports_commodities:
                        parts.append(f"Main exports: {exports_commodities}")
                    if imports_partners:
                        parts.append(f"Import partners: {imports_partners}")
                    if imports_commodities:
                        parts.append(f"Main imports: {imports_commodities}")
                    return {
                        "type": "trade_info",
                        "file": str(ref_path),
                        "country_data": {
                            "country": country_name,
                            "iso3": iso3,
                            "exports_partners": exports_partners,
                            "exports_commodities": exports_commodities,
                            "imports_partners": imports_partners,
                            "imports_commodities": imports_commodities,
                            "formatted": f"{country_name} Trade - " + "; ".join(parts),
                        },
                    }

    government_keywords = ["government", "political", "constitution", "president", "parliament", "legislature"]
    if any(kw in query_lower for kw in government_keywords):
        iso3, country_name = ensure_country_context()
    if iso3 and any(kw in query_lower for kw in government_keywords):
        ref_path = reference_dir / "world_factbook_text.json"
        if ref_path.exists():
            data = load_reference_file(ref_path) or {}
            countries = data.get("countries", {})
            if iso3 in countries:
                country_data = countries[iso3]
                executive = country_data.get("executive_branch", "")
                legislative = country_data.get("legislative_branch", "")
                constitution = country_data.get("constitution", "")
                if executive or legislative or constitution:
                    parts = []
                    if executive:
                        parts.append(f"Executive: {executive[:300]}")
                    if legislative:
                        parts.append(f"Legislature: {legislative[:200]}")
                    return {
                        "type": "government_info",
                        "file": str(ref_path),
                        "country_data": {
                            "country": country_name,
                            "iso3": iso3,
                            "executive": executive,
                            "legislative": legislative,
                            "constitution": constitution,
                            "formatted": f"{country_name} Government - " + "; ".join(parts),
                        },
                    }

    catalog = load_catalog()
    if catalog:
        for source in catalog.get("sources", []):
            source_id = source.get("source_id") or ""
            source_name = (source.get("source_name") or "").lower()
            keywords = [k.lower() for k in source.get("keywords", []) if k]
            topic_tags = [t.lower() for t in source.get("topic_tags", []) if t]

            if not source_id:
                continue

            if source_id.lower() in query_lower or source_name in query_lower:
                source_path = get_source_path(source_id)
                if source_path:
                    ref_path = source_path / "reference.json"
                    if ref_path.exists():
                        return {
                            "type": "data_source",
                            "source_id": source_id,
                            "file": str(ref_path),
                            "content": load_reference_file(ref_path),
                        }

            for kw in keywords + topic_tags:
                if kw and len(kw) > 2 and kw in query_lower:
                    source_path = get_source_path(source_id)
                    if source_path:
                        ref_path = source_path / "reference.json"
                        if ref_path.exists():
                            return {
                                "type": "data_source",
                                "source_id": source_id,
                                "file": str(ref_path),
                                "content": load_reference_file(ref_path),
                            }

    return None
