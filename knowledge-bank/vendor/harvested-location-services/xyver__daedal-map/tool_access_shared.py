"""Authored source of truth for per-tool access gates.

This is the tool-level twin of ``pack_registry_shared.PACK_REGISTRY``. Pack
pricing answers "is this dataset paid?"; this answers "how much of this tool can
one caller use for free, and what does paying buy?".

Three product rules this file encodes:

1. **Downloads and samples stay free.** Nothing here gates static downloads or
   sample data. These limits only apply to hosted MCP/API execution.
2. **Paying buys hosted execution, not ownership.** A dual-lane ``paid_bulk``
   tool returns the same answer to everyone; payment permits more hosted work.
   Create-job tools may bill from their first charge unit after a free estimate.
   There is no paid-only field, row, identifier, or region.
3. **License permission is the ceiling.** A tool may only be ``paid_bulk`` when
   the geometry banks or packs behind it carry ``permission: "paid"``. If the
   upstream license forbids paid hosted service, the tool stays free no matter
   what is authored here. See ``licensing_permits_paid_bulk``.

These are entitlement limits, not safety ceilings. Safety ceilings live in the
runtime read/admission path; see ``docs/caps_and_limits.md``.

These are also product-lane defaults, not customer-specific contracts. A future
trusted user/org/API-key limit profile may specialize them, but the runtime must
clamp every such override to its non-bypassable safety ceiling. Credit balance
authorizes a quoted call; it does not change the caller's plan tier.

Lanes are ``free``, ``account``, and ``paid``, matching
``CallerIdentity.access_tier``.

To change a per-call item limit: edit ``free_item_limit`` /
``account_item_limit`` / ``paid_item_limit`` here.
To change the default hosted tool-call rates: edit
``HOSTED_TOOL_RATE_LIMIT_DEFAULTS`` here. A tool may override those defaults
with its own ``rate_limits`` entry in ``TOOL_ACCESS_REGISTRY``.
To change a conversion lane's price: edit ``IDENTIFIER_RATE_USD_PER_100`` or
``POINT_RATE_USD_PER_100`` below and bump the affected ``pricing_version``s.
To change any other price: edit the authored ``price`` here, set the canonical micro-USD
environment override, or activate a revisioned dashboard pricing override.
To swap a tool between free and paid: change ``pricing`` here, and nothing else.

Env vars still override at runtime for incident response and load testing:
``MCP_TOOL_BATCH_LIMIT_<TOOL_NAME>`` first, then the legacy compatibility names
listed per tool, then the value authored here.

Full free<->paid checklist (enforcement, advertised pricing, license, public
docs, catalog surfaces):
county-map-private/docs/future/API/mcp_publishing.md section 15.
"""

from __future__ import annotations

import os
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


MICRO_USD_PER_DISPLAY_CREDIT = 10_000
CREDIT_PRICE_QUANTUM_MICRO_USD = 1_000
CREDIT_DEFINITION = "One DaedalMap credit equals one US cent ($0.01)."
ENTERPRISE_CONTACT = "contact@daedalmap.com"


def hosted_commercial_policy() -> dict:
    """Public lane semantics shared by MCP cards, docs, and catalog renderers."""
    return {
        "credit_definition": {
            "usd_per_credit": 0.01,
            "micro_usd_per_credit": MICRO_USD_PER_DISPLAY_CREDIT,
            "statement": CREDIT_DEFINITION,
        },
        "governance": {
            "compute_cost_role": "floor",
            "substitution_value_role": "ceiling",
            "rule": "Price at or above measured delivery cost and at or below the value of the work replaced.",
        },
        "access_lanes": {
            "downloads": "free",
            "hosted_discovery": "free",
            "hosted_execution": "metered only when the tool and material policy permit it",
            "enterprise": {
                "mode": "contract_or_invoice",
                "contact": ENTERPRISE_CONTACT,
            },
        },
    }


def quantize_credit_price(amount_micro_usd: int) -> int:
    """Round a positive price to 0.1 displayed credit using integer math."""
    amount = max(0, int(amount_micro_usd or 0))
    if amount == 0:
        return 0
    quantum = CREDIT_PRICE_QUANTUM_MICRO_USD
    return max(quantum, ((amount + quantum // 2) // quantum) * quantum)


# Explicit conversion-tool prices start with ``paid``. Material-backed tools
# use ``by_pack`` / ``by_material`` and let the catalog's legal policy decide
# whether the hosted call is metered, forced free, or blocked.
PRICING_FREE = "free"
PRICING_PAID_BULK = "paid_bulk_x402_base_usdc"
PRICING_BY_PACK = "by_pack"
PRICING_BY_MATERIAL = "by_material"

# Tool families. "geography" is the geometry/loc_id utility family; "discovery"
# is the free catalog/helper surface; "dataset" tools price through the pack
# registry instead of here.
FAMILY_GEOGRAPHY = "geography"
FAMILY_DISCOVERY = "discovery"
FAMILY_DATASET = "dataset"


# Named conversion rates, in USD per 100 successfully resolved items. These
# are the two levers for the loc_id conversion lanes; every tool below reads
# one of them, so changing a rate here reprices every tool in that lane.
#
# Documented rate card and decision history:
# county-map-private/docs/future/API/agent_api_monetization_plan.md, "Tool
# rates". Keep that table in step with these values. Runtime overrides
# (MCP_TOOL_PRICE_*_<TOOL>, legacy_price_env names, and the Access & Payment
# dashboard) win over these values without a code change.
#
# Identifier lane: external code to loc_id (convert_reference,
# create_conversion_job). This is an index join, not a
# spatial computation.
IDENTIFIER_RATE_USD_PER_100 = 0.05
# Point lane: coordinate to loc_id chain (resolve_point). Point-in-polygon
# work reads geometry, so it is priced above the identifier join.
POINT_RATE_USD_PER_100 = 0.10
# Hosted retrieval is a managed-service fee, not a different data product.
# These two levers price material-aware MCP calls while downloads and local
# execution remain outside this gate.
HOSTED_RETRIEVAL_BASE_USD = 0.01
HOSTED_RETRIEVAL_RATE_USD_PER_100 = 0.01
# Fixed charge added to every paid call once it exceeds its free allowance.
PAID_CALL_BASE_USD = 0.01


# Authored hosted product defaults. This is the rate-limit equivalent of the
# named price levers above: edit these three records to retune every hosted MCP
# tool. Per-tool ``rate_limits`` entries may specialize them. Environment and
# revisioned operator-policy overrides remain available for operations without
# creating another authored default.
#
# ``paid`` is the product name. The external policy and legacy environment
# contract still call this tier ``plus``; the resolver below translates it.
HOSTED_TOOL_RATE_LIMIT_DEFAULTS: dict[str, dict[str, int]] = {
    "free": {"limit": 10, "window_seconds": 60},
    "account": {"limit": 60, "window_seconds": 60},
    "paid": {"limit": 120, "window_seconds": 60},
}

# Aggregate MCP transport allowance. These limits include protocol traffic and
# calls across all tools, so each tier has headroom above its per-tool rate.
# The separate server-safety fuse remains the absolute ceiling.
HOSTED_MCP_SURFACE_RATE_LIMIT_DEFAULTS: dict[str, dict[str, int]] = {
    "free": {"limit": 30, "window_seconds": 60},
    "account": {"limit": 90, "window_seconds": 60},
    "paid": {"limit": 180, "window_seconds": 60},
}


TOOL_ACCESS_REGISTRY: dict[str, dict] = {
    "get_tool_help": {
        "family": FAMILY_DISCOVERY,
        "capability_id": "tool_help_discovery",
        "pricing": PRICING_FREE,
        "notes": "Blind-caller help must stay free on every facade.",
    },
    "resolve_point": {
        "family": FAMILY_GEOGRAPHY,
        "capability_id": "point_lookup",
        "pricing": PRICING_PAID_BULK,
        "item_field": "points",
        "free_item_limit": 100,
        "account_item_limit": 1000,
        "paid_item_limit": 10000,
        "legacy_limit_env": ("POINT_LOOKUP_BATCH_LIMIT",),
        "legacy_paid_limit_env": ("POINT_LOOKUP_PAID_BATCH_LIMIT",),
        "price": {"base_usd": PAID_CALL_BASE_USD, "per_unit_usd": POINT_RATE_USD_PER_100 / 100},
        "pricing_version": "geography-tools-2026-09-18.1",
        "meter": {"unit": "resolved_point", "items_per_charge_unit": 1},
        "legacy_price_env": {
            "base_usd": ("POINT_LOOKUP_PAID_BASE_USD",),
            "per_unit_usd": ("POINT_LOOKUP_PAID_PER_POINT_USD",),
        },
        "notes": "One coordinate stays free; point arrays use the authored bulk lanes.",
    },
    "resolve_deep_point": {
        "family": FAMILY_GEOGRAPHY,
        "capability_id": "deep_point_lookup",
        "pricing": PRICING_FREE,
        "item_field": "points",
        "free_item_limit": 100,
        "paid_item_limit": 100,
        "notes": "Initial technical rollout is bounded to one Admin1 partition and 100 points; payment policy comes later.",
    },
    "get_geometry": {
        "family": FAMILY_GEOGRAPHY,
        "capability_id": "geometry_lookup",
        "pricing": PRICING_BY_MATERIAL,
        "price": {
            "base_usd": HOSTED_RETRIEVAL_BASE_USD,
            "per_unit_usd": HOSTED_RETRIEVAL_RATE_USD_PER_100 / 100,
        },
        "pricing_version": "hosted-retrieval-2026-09-21.1",
        "meter": {"unit": "geometry_result", "items_per_charge_unit": 1},
        "item_field": "loc_ids",
        "free_item_limit": 1000,
        "paid_item_limit": 25000,
        # Polygons are payload-heavy, so they carry their own centrally
        # authored cap instead of an inline route default.
        "sub_limits": {
            "polygons": {
                "free_item_limit": 100,
                "limit_env": "MCP_TOOL_POLYGON_BATCH_LIMIT_GET_GEOMETRY",
            },
        },
        "legacy_limit_env": ("GEOMETRY_GET_BATCH_LIMIT",),
    },
    "get_loc_id_info": {
        "family": FAMILY_GEOGRAPHY,
        "capability_id": "loc_id_metadata",
        "pricing": PRICING_FREE,
        "item_field": "loc_ids",
        "free_item_limit": 100,
        "paid_item_limit": 2500,
        "legacy_limit_env": ("LOC_ID_INFO_BATCH_LIMIT",),
        # include_references fans out across bridge artifacts, so it is capped
        # lower than plain metadata enrichment.
        "sub_limits": {
            "references": {
                "free_item_limit": 25,
                "limit_env": "MCP_TOOL_REFERENCES_BATCH_LIMIT_LOC_ID_INFO",
                "legacy_limit_env": ("LOC_ID_INFO_REFERENCES_BATCH_LIMIT",),
            },
        },
    },
    "identify_reference_system": {
        "family": FAMILY_GEOGRAPHY,
        "capability_id": "reference_system_identification",
        "pricing": PRICING_FREE,
        "item_field": "identifiers",
        "free_item_limit": 100,
        "paid_item_limit": 2500,
        "legacy_limit_env": ("REFERENCE_IDENTIFY_BATCH_LIMIT",),
    },
    "identify_dataset_geography": {
        "family": FAMILY_GEOGRAPHY,
        "capability_id": "dataset_geography_identification",
        "pricing": PRICING_FREE,
        "item_field": "columns",
        "free_item_limit": 64,
        "paid_item_limit": 64,
    },
    "convert_reference": {
        "family": FAMILY_GEOGRAPHY,
        "capability_id": "reference_conversion",
        "price": {"base_usd": PAID_CALL_BASE_USD, "per_unit_usd": IDENTIFIER_RATE_USD_PER_100 / 100},
        "pricing_version": "geography-tools-2026-09-18.1",
        "meter": {"unit": "converted_reference", "items_per_charge_unit": 1},
        "pricing": PRICING_PAID_BULK,
        "item_field": "items",
        "free_item_limit": 100,
        "account_item_limit": 1000,
        "paid_item_limit": 2500,
        "legacy_limit_env": ("REFERENCE_CONVERT_BATCH_LIMIT",),
    },
    "compare_geographies": {
        "family": FAMILY_GEOGRAPHY,
        "capability_id": "geography_comparison",
        "pricing": PRICING_FREE,
        "item_field": "items",
        "free_item_limit": 100,
        "paid_item_limit": 2500,
    },
    "resolve_loc_id_scope": {
        "family": FAMILY_GEOGRAPHY,
        "capability_id": "loc_id_scope",
        "pricing": PRICING_FREE,
        "item_field": "limit",
        "free_item_limit": 100,
        "paid_item_limit": 5000,
        "trusted_item_limit": 100000,
        "trusted_limit_env": "MCP_TOOL_TRUSTED_BATCH_LIMIT_RESOLVE_LOC_ID_SCOPE",
        "legacy_limit_env": ("LOC_ID_SCOPE_LIMIT",),
    },
    # ---- geography: quote/execute pair. Hosted v0 has an adjustable inline
    # ceiling; larger work is directed to downloads or the custom builder.
    "estimate_geometry_package": {
        "family": FAMILY_GEOGRAPHY,
        "capability_id": "geometry_package_estimate",
        "pricing": PRICING_FREE,
        "notes": "Quotes must stay free; this is the measurable boundary before any charge.",
    },
    # Charge-unit priced: geometry_tool_jobs already computes charge_units
    # (one unit per 10 polygons, or per 100 metadata rows). These rates attach a
    # price to that existing meter. Estimates stay free; only creation bills.
    "create_geometry_export": {
        "price": {"base_usd": 0.01, "per_unit_usd": 0.004},
        "charge_unit": "charge_units",
        "pricing_version": "geography-tools-2026-08-16.1",
        "meter": {
            "unit": "geometry_charge_unit",
            "polygon_items_per_charge_unit": 10,
            "metadata_items_per_charge_unit": 100,
        },
        "family": FAMILY_GEOGRAPHY,
        "capability_id": "geometry_export",
        "pricing": PRICING_PAID_BULK,
        "inline_item_limit": 250,
        "legacy_limit_env": ("GEOMETRY_EXPORT_INLINE_LIMIT",),
    },
    "estimate_conversion_job": {
        "family": FAMILY_GEOGRAPHY,
        "capability_id": "conversion_job_estimate",
        "pricing": PRICING_FREE,
        "notes": "Quotes must stay free.",
    },
    "create_conversion_job": {
        # One charge unit is 100 successfully resolved references, so the unit
        # price is the identifier rate itself.
        "price": {"base_usd": PAID_CALL_BASE_USD, "per_unit_usd": IDENTIFIER_RATE_USD_PER_100},
        "charge_unit": "charge_units",
        "pricing_version": "geography-tools-2026-09-18.1",
        "meter": {"unit": "conversion_charge_unit", "items_per_charge_unit": 100},
        "family": FAMILY_GEOGRAPHY,
        "capability_id": "conversion_job",
        "pricing": PRICING_PAID_BULK,
        "inline_item_limit": 7500,
        "legacy_limit_env": ("CONVERSION_JOB_INLINE_LIMIT",),
    },
    "get_job_status": {
        "family": FAMILY_GEOGRAPHY,
        "capability_id": "geometry_job_status",
        "pricing": PRICING_FREE,
        "notes": "Polling a job you already paid for must never be gated.",
    },
    # ---- discovery helpers: always free. Gating these would make the catalog
    # undiscoverable and break the funnel. ----
    "get_catalog": {
        "family": FAMILY_DISCOVERY,
        "capability_id": "catalog_discovery",
        "pricing": PRICING_FREE,
    },
    "get_pack": {
        "family": FAMILY_DISCOVERY,
        "capability_id": "pack_detail_discovery",
        "pricing": PRICING_FREE,
    },
    "get_live_earthquake_events": {
        "family": FAMILY_DISCOVERY,
        "capability_id": "live_earthquake_lookup",
        "pricing": PRICING_FREE,
    },
    "get_live_volcano_events": {
        "family": FAMILY_DISCOVERY,
        "capability_id": "live_volcano_lookup",
        "pricing": PRICING_FREE,
    },
    "get_event": {
        "family": FAMILY_DATASET,
        "capability_id": "disaster_event_lookup",
        "pricing": PRICING_BY_PACK,
        "price": {
            "base_usd": HOSTED_RETRIEVAL_BASE_USD,
            "per_unit_usd": HOSTED_RETRIEVAL_RATE_USD_PER_100 / 100,
        },
        "pricing_version": "hosted-retrieval-2026-09-21.1",
        "meter": {"unit": "event_lookup", "items_per_charge_unit": 1},
        "item_field": "limit",
        "free_item_limit": 500,
        "paid_item_limit": 500,
        "sub_limits": {
            "geometry": {
                "free_item_limit": 25,
                "limit_env": "MCP_TOOL_GEOMETRY_BATCH_LIMIT_GET_EVENT",
            },
        },
        "notes": "One exact event lookup; companion rows and geometry are explicit, centrally bounded includes.",
    },
    # ---- dataset tools: priced by pack, not here. Listed so the universe is
    # complete and nothing is silently ungoverned. ----
    "get_data": {"family": FAMILY_DATASET, "capability_id": "dataset_query", "pricing": PRICING_BY_PACK},
}


def tool_ids() -> tuple[str, ...]:
    return tuple(TOOL_ACCESS_REGISTRY)


def tool_profile(tool_name: str) -> dict:
    return TOOL_ACCESS_REGISTRY.get(str(tool_name or "").strip(), {})


def tool_capability_id(tool_name: str) -> str:
    return str(tool_profile(tool_name).get("capability_id") or tool_name or "").strip()


def tool_family(tool_name: str) -> str:
    return str(tool_profile(tool_name).get("family") or "").strip()


def tool_pricing(tool_name: str) -> str:
    return str(tool_profile(tool_name).get("pricing") or PRICING_FREE).strip()


def tool_public_pricing(tool_name: str) -> str:
    """Describe access without exposing a dormant settlement implementation."""
    pricing = tool_pricing(tool_name)
    return "free_with_paid_bulk" if pricing.startswith("paid_bulk_") else pricing


def tool_is_paid_bulk(tool_name: str) -> bool:
    """True for the explicit paid conversion/bulk lane.

    Material-priced tools are authorized separately against their selected
    pack or geometry banks; they are not unconditional bulk conversions here.
    """
    return tool_pricing(tool_name).startswith("paid")


def tool_free_item_limit(tool_name: str) -> int | None:
    value = tool_profile(tool_name).get("free_item_limit")
    return int(value) if isinstance(value, int) else None


def tool_paid_item_limit(tool_name: str) -> int | None:
    value = tool_profile(tool_name).get("paid_item_limit")
    return int(value) if isinstance(value, int) else None


# Fallback multiple over the free limit when a tool does not author
# ``account_item_limit``.
ACCOUNT_ITEM_LIMIT_MULTIPLIER = 10


def tool_account_item_limit(tool_name: str) -> int | None:
    """Account-lane item limit.

    Authored ``account_item_limit`` wins; otherwise the free limit scaled by
    ``ACCOUNT_ITEM_LIMIT_MULTIPLIER``, clamped to the paid limit.
    """
    authored = tool_profile(tool_name).get("account_item_limit")
    if isinstance(authored, int):
        return int(authored)
    free = tool_free_item_limit(tool_name)
    if free is None:
        return None
    scaled = int(free) * ACCOUNT_ITEM_LIMIT_MULTIPLIER
    paid = tool_paid_item_limit(tool_name)
    return min(scaled, int(paid)) if paid is not None else scaled


def tool_authored_rate_limit(tool_name: str, *, lane: str = "free") -> tuple[int, int]:
    """Return the central authored call rate for one hosted product lane."""
    normalized = str(lane or "free").strip().lower()
    if normalized == "plus":
        normalized = "paid"
    if normalized not in HOSTED_TOOL_RATE_LIMIT_DEFAULTS:
        normalized = "free"
    defaults = HOSTED_TOOL_RATE_LIMIT_DEFAULTS[normalized]
    profile_rates = tool_profile(tool_name).get("rate_limits")
    profile_rates = profile_rates if isinstance(profile_rates, dict) else {}
    override = profile_rates.get(normalized)
    override = override if isinstance(override, dict) else {}
    return (
        max(1, int(override.get("limit") or defaults["limit"])),
        max(1, int(override.get("window_seconds") or defaults["window_seconds"])),
    )


def tool_effective_rate_limit(tool_name: str, *, lane: str = "free") -> tuple[int, int]:
    """Resolve one hosted tool-call rate through the standard override stack.

    Precedence is revisioned operator policy, environment, per-tool registry,
    then ``HOSTED_TOOL_RATE_LIMIT_DEFAULTS``. Local-installed and trusted QA
    bypasses are decided by the caller before this resolver is used.
    """
    normalized = str(lane or "free").strip().lower()
    if normalized == "plus":
        normalized = "paid"
    if normalized not in HOSTED_TOOL_RATE_LIMIT_DEFAULTS:
        normalized = "free"
    suffix = "".join(ch if ch.isalnum() else "_" for ch in str(tool_name or "").upper()).strip("_")
    authored_limit, authored_window = tool_authored_rate_limit(tool_name, lane=normalized)
    window_seconds = (
        _env_int_optional(f"MCP_TOOL_RATE_WINDOW_SECONDS_{suffix}")
        or _env_int_optional("MCP_LIVE_TOOL_RATE_WINDOW_SECONDS")
        or authored_window
    )
    free_authored, _ = tool_authored_rate_limit(tool_name, lane="free")
    free_limit = (
        _env_int_optional(f"MCP_TOOL_RATE_LIMIT_{suffix}")
        or _env_int_optional("MCP_LIVE_TOOL_RATE_LIMIT")
        or free_authored
    )
    if normalized == "account":
        resolved_limit = (
            _env_int_optional(f"MCP_TOOL_RATE_LIMIT_{suffix}_ACCOUNT")
            or _env_int_optional("MCP_TOOL_RATE_LIMIT_ACCOUNT")
            or max(free_limit, authored_limit)
        )
        policy_tier = "account"
    elif normalized == "paid":
        resolved_limit = (
            _env_int_optional(f"MCP_TOOL_RATE_LIMIT_{suffix}_PLUS")
            or _env_int_optional("MCP_TOOL_RATE_LIMIT_PLUS")
            or max(free_limit, authored_limit)
        )
        policy_tier = "plus"
    else:
        resolved_limit = free_limit
        policy_tier = "free"
    try:
        from access_policy_shared import tool_rate_limit as operator_tool_rate_limit

        return operator_tool_rate_limit(
            tool_name,
            policy_tier,
            default_limit=max(1, int(resolved_limit)),
            default_window_seconds=max(1, int(window_seconds)),
        )
    except Exception:
        return max(1, int(resolved_limit)), max(1, int(window_seconds))


def _price_env_names(tool_name: str, field: str) -> tuple[str, ...]:
    """Env override names for one tool's price field, most specific first."""
    suffix = str(tool_name or "").strip().upper()
    generic = f"MCP_TOOL_PRICE_{field.upper()}_{suffix}"
    legacy = tool_profile(tool_name).get("legacy_price_env") or {}
    legacy_names = legacy.get(field) if isinstance(legacy, dict) else ()
    compatibility = (
        (f"MCP_TOOL_PRICE_PER_ITEM_USD_{suffix}",)
        if field == "per_unit_usd" else ()
    )
    return (generic, *compatibility, *(str(name) for name in legacy_names or ()))


def tool_price(tool_name: str) -> dict:
    """Resolve one tool's price. Registry value is the default; env wins.

    Pricing is a lever, not a constant: every field can be retuned per tool
    through the environment without a deploy, and a tool with no authored price
    resolves to zero so an unpriced tool can never silently start charging.
    """
    authored = tool_profile(tool_name).get("price")
    authored = authored if isinstance(authored, dict) else {}
    out: dict[str, float] = {}
    for field in ("base_usd", "per_unit_usd"):
        legacy_field = "per_item_usd" if field == "per_unit_usd" else field
        value = float(authored.get(field, authored.get(legacy_field)) or 0.0)
        for env_name in _price_env_names(tool_name, field):
            raw = str(os.getenv(env_name, "") or "").strip()
            if raw:
                try:
                    value = float(raw)
                except ValueError:
                    continue
                break
        out[field] = value
    # Compatibility alias for older discovery consumers. New code and copy
    # should say unit because a unit may represent 1, 10, or 100 items.
    out["per_item_usd"] = out["per_unit_usd"]
    return out


def _operator_price_override(tool_name: str) -> tuple[dict, str]:
    """Return the active dashboard override and its revision, if present."""
    try:
        from access_policy_shared import load_access_policy

        policy = load_access_policy()
    except Exception:
        return {}, ""
    pricing = policy.get("pricing") if isinstance(policy, dict) else {}
    tools = pricing.get("tools") if isinstance(pricing, dict) else {}
    entry = tools.get(str(tool_name or "").strip().lower()) if isinstance(tools, dict) else None
    revision = str(policy.get("policy_revision") or "").strip() if isinstance(policy, dict) else ""
    return (dict(entry), revision) if isinstance(entry, dict) else ({}, revision)


def _usd_to_micro_usd(value) -> int:
    try:
        amount = Decimal(str(value or 0)) * Decimal("1000000")
    except (InvalidOperation, TypeError, ValueError):
        return 0
    return max(0, int(amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP)))


def _env_int_optional(name: str) -> int | None:
    raw = str(os.getenv(name, "") or "").strip()
    if not raw:
        return None
    try:
        return max(0, int(raw))
    except ValueError:
        return None


def tool_price_micro_usd(tool_name: str) -> dict:
    """Integer pricing snapshot used by estimates, authorization, and capture.

    Integer micro-USD keeps every surface on the same rounding rule. The
    canonical integer env vars are preferred; the older USD env vars remain
    supported through ``tool_price`` so operators can migrate without a flag
    day.
    """
    suffix = "".join(ch if ch.isalnum() else "_" for ch in str(tool_name or "").upper()).strip("_")
    authored = tool_price(tool_name)
    base = _env_int_optional(f"MCP_TOOL_PRICE_BASE_MICRO_USD_{suffix}")
    per_unit = _env_int_optional(f"MCP_TOOL_PRICE_PER_UNIT_MICRO_USD_{suffix}")
    resolved = {
        "base_micro_usd": _usd_to_micro_usd(authored.get("base_usd")) if base is None else base,
        "per_unit_micro_usd": _usd_to_micro_usd(authored.get("per_unit_usd")) if per_unit is None else per_unit,
    }
    override, _revision = _operator_price_override(tool_name)
    for field in ("base_micro_usd", "per_unit_micro_usd"):
        value = override.get(field)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            resolved[field] = value
    resolved["source"] = "operator_policy" if override else ("environment" if base is not None or per_unit is not None else "registry")
    return resolved


def tool_pricing_version(tool_name: str) -> str:
    suffix = "".join(ch if ch.isalnum() else "_" for ch in str(tool_name or "").upper()).strip("_")
    override = str(os.getenv(f"MCP_TOOL_PRICING_VERSION_{suffix}", "") or "").strip()
    if override:
        return override
    price_override, revision = _operator_price_override(tool_name)
    if price_override:
        authored = str(price_override.get("pricing_version") or "").strip()
        return authored or f"operator-policy:{revision or 'unknown'}"
    return str(tool_profile(tool_name).get("pricing_version") or "unpriced-v0")


def tool_meter(tool_name: str) -> dict:
    value = tool_profile(tool_name).get("meter")
    return dict(value) if isinstance(value, dict) else {"unit": "item", "items_per_charge_unit": 1}


def tool_charge_units(
    tool_name: str,
    item_count: int,
    *,
    divisor_field: str = "items_per_charge_unit",
    minimum: bool = False,
) -> int:
    """Convert physical items into the tool's authored billable units."""
    meter = tool_meter(tool_name)
    divisor = max(1, int(meter.get(divisor_field) or 1))
    count = max(0, int(item_count or 0))
    units = (count + divisor - 1) // divisor
    return max(1, units) if minimum and count else units


def tool_charge_quote(tool_name: str, charge_units: int) -> dict:
    """Quote an already-metered job through the same tool pricing authority."""
    units = max(0, int(charge_units or 0))
    return {**tool_quote(tool_name, units, free_limit=0), "charge_units": units}


def resize_charge_quote(quote: dict, charge_units: int) -> dict:
    """Apply actual units to an immutable estimate-rate snapshot.

    Execution may finish with fewer successful units than were reserved. Using
    the estimate's rates and version prevents an operator price change during a
    request from repricing or invalidating that in-flight job.
    """
    units = max(0, int(charge_units or 0))
    fallback = tool_price_micro_usd(str(quote.get("tool_name") or ""))
    base = max(0, int(quote.get("base_micro_usd", fallback["base_micro_usd"]) or 0))
    per_unit = max(0, int(quote.get("per_unit_micro_usd", fallback["per_unit_micro_usd"]) or 0))
    amount = quantize_credit_price(base + units * per_unit if units else 0)
    resized = dict(quote)
    resized.update({
        "quantity": units,
        "free_quantity": 0,
        "billable_quantity": units,
        "charge_units": units,
        "base_micro_usd": base,
        "per_unit_micro_usd": per_unit,
        "amount_usdc_base_units": amount,
        "estimated_price_usd": amount / 1_000_000,
        "price_credits": amount / MICRO_USD_PER_DISPLAY_CREDIT,
        "price_display": f"${amount / 1_000_000:.6f}".rstrip("0").rstrip("."),
    })
    return resized


def tool_effective_item_limit(tool_name: str, *, lane: str = "free", default: int | None = None) -> int | None:
    """Resolve one adjustable per-call limit from the shared registry.

    ``lane`` is ``free``, ``account``, ``paid``, or ``inline``. Every lane has
    one canonical env name and may retain authored legacy names for
    compatibility.
    """
    normalized_lane = str(lane or "free").strip().lower()
    suffix = "".join(ch if ch.isalnum() else "_" for ch in str(tool_name or "").upper()).strip("_")
    if normalized_lane == "paid":
        env_names = (f"MCP_TOOL_PAID_BATCH_LIMIT_{suffix}", *tuple(tool_profile(tool_name).get("legacy_paid_limit_env") or ()))
        authored = tool_paid_item_limit(tool_name)
    elif normalized_lane == "account":
        env_names = (f"MCP_TOOL_ACCOUNT_BATCH_LIMIT_{suffix}",)
        authored = tool_account_item_limit(tool_name)
        if authored is None:
            authored = tool_free_item_limit(tool_name)
    else:
        env_names = (f"MCP_TOOL_BATCH_LIMIT_{suffix}", *tool_legacy_limit_env(tool_name))
        authored = tool_inline_item_limit(tool_name) if normalized_lane == "inline" else tool_free_item_limit(tool_name)
        if authored is None and normalized_lane == "free":
            authored = tool_inline_item_limit(tool_name)
    for env_name in env_names:
        value = _env_int_optional(str(env_name))
        if value is not None:
            return max(1, value)
    value = authored if authored is not None else default
    return max(1, int(value)) if value is not None else None


def tool_quote(tool_name: str, item_count: int, free_limit: int | None = None) -> dict:
    """Exact price for one call.

    The billable quantity is bounded by ``paid_item_limit`` rather than by a
    money ceiling. Binding the cap to data size keeps one lever instead of two
    and means raising throughput does not silently give the extra work away.
    """
    free = tool_free_item_limit(tool_name) if free_limit is None else free_limit
    free = int(free or 0)
    price = tool_price_micro_usd(tool_name)
    meter = tool_meter(tool_name)
    billable = max(0, int(item_count) - free)
    amount_micro_usd = quantize_credit_price(
        price["base_micro_usd"] + billable * price["per_unit_micro_usd"] if billable else 0
    )
    items_per_unit = meter.get("items_per_charge_unit")
    per_item_usd = (
        price["per_unit_micro_usd"] / max(1, int(items_per_unit)) / 1_000_000
        if isinstance(items_per_unit, int) and not isinstance(items_per_unit, bool)
        else None
    )
    return {
        "capability_id": tool_capability_id(tool_name),
        "tool_name": str(tool_name or "").strip(),
        "pricing_version": f"{tool_pricing_version(tool_name)}+credit-q1000",
        "meter": meter,
        "quantity": int(item_count),
        "free_quantity": free,
        "billable_quantity": billable,
        "base_micro_usd": price["base_micro_usd"],
        "per_unit_micro_usd": price["per_unit_micro_usd"],
        "pricing_source": price["source"],
        "amount_usdc_base_units": amount_micro_usd,
        "base_usd": price["base_micro_usd"] / 1_000_000,
        "per_item_usd": per_item_usd,
        "per_unit_usd": price["per_unit_micro_usd"] / 1_000_000,
        "estimated_price_usd": amount_micro_usd / 1_000_000,
        "price_credits": amount_micro_usd / MICRO_USD_PER_DISPLAY_CREDIT,
        "price_display": f"${amount_micro_usd / 1_000_000:.6f}".rstrip("0").rstrip("."),
        "item_limit": tool_paid_item_limit(tool_name),
    }


def tool_payment_required_payload(
    tool_name: str,
    item_count: int,
    *,
    free_limit: int,
    paid_limit: int,
    request_id: str | None = None,
    batch_id: str | None = None,
) -> dict:
    """Build the shared REST/MCP challenge envelope for a hosted tool."""
    quote = {
        **tool_quote(tool_name, item_count, free_limit=free_limit),
        "payment_rails": ["account_credit"],
        "status": "quote_only",
    }
    return {
        "request_id": request_id,
        "batch_id": batch_id,
        "payment_required": True,
        "quote": quote,
        "limits": {"free_batch_limit": free_limit, "paid_batch_limit": paid_limit},
        "retry_hint": "Retry the same request with an account API key that holds enough credit.",
        "error": {
            "code": "payment_required",
            "message": f"{item_count} items exceeds the free preview limit of {free_limit}.",
        },
    }


def tool_charge_unit(tool_name: str) -> str:
    """Name of the response field this tool bills on, if it is unit-metered.

    Export and conversion tools bill per charge unit (one per 10 polygons, or
    per 100 rows) rather than per requested item, because their cost tracks
    payload produced rather than arguments supplied.
    """
    return str(tool_profile(tool_name).get("charge_unit") or "").strip()


def tool_inline_item_limit(tool_name: str) -> int | None:
    value = tool_profile(tool_name).get("inline_item_limit")
    return int(value) if isinstance(value, int) else None


def tool_legacy_limit_env(tool_name: str) -> tuple[str, ...]:
    value = tool_profile(tool_name).get("legacy_limit_env") or ()
    return tuple(str(name) for name in value)


def tool_sub_limit(tool_name: str, sub_key: str) -> dict:
    subs = tool_profile(tool_name).get("sub_limits")
    if not isinstance(subs, dict):
        return {}
    entry = subs.get(str(sub_key or "").strip())
    return entry if isinstance(entry, dict) else {}


def free_tool_ids() -> tuple[str, ...]:
    return tuple(name for name in TOOL_ACCESS_REGISTRY if not tool_is_paid_bulk(name))


def paid_bulk_tool_ids() -> tuple[str, ...]:
    return tuple(name for name in TOOL_ACCESS_REGISTRY if tool_is_paid_bulk(name))


def licensing_permits_paid_bulk(permissions) -> bool:
    """True only when every contributing source/bank permits paid hosted use.

    ``permissions`` is the set of ``permission`` values behind the tool, taken
    from pack metadata or geometry bank ``source_license`` entries. The rule
    from docs/future/open_data_business_model.md is deliberately strict:

    - ``paid``  -> the licence allows paid hosted API/MCP lanes
    - ``free``  -> usable in free lanes only; must not sit behind paid access
    - ``other`` -> unresolved research state; never treat as paid

    One ``free`` or unresolved contributor disqualifies the whole tool, because
    a bulk call can span every bank behind it.
    """
    values = {str(value or "").strip().lower() for value in (permissions or [])}
    if not values:
        return False
    return values == {"paid"}
