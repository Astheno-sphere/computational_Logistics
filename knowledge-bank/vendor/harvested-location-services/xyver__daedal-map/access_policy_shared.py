"""Runtime access-policy overlay shared by data packs and geometry tools.

Pack and geometry manifests contain durable facts: source provenance, licence
conditions, release clearance, stable capability ids, and default meters.  The
operator policy in this module contains mutable deployment choices: whether a
normally metered capability is temporarily free, which audience may call it,
and the active rate-limit profile.

The policy is loaded at request time through a small mtime-aware cache.  An
operator can therefore change access without rebuilding data, geometry, or an
agent catalog.  Precedence is:

    legal/publication ceiling -> operator access -> entitlement -> settlement

An operator override may waive payment.  It can never make a source eligible
for paid use when its factual licence envelope does not permit that use.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable


POLICY_SCHEMA_VERSION = "1.0.0"
POLICY_JSON_ENV = "DAEDALMAP_ACCESS_POLICY_JSON"
POLICY_FILE_ENV = "DAEDALMAP_ACCESS_POLICY_FILE"
RUNTIME_POLICY_FILE_ENV = "DAEDALMAP_ACCESS_POLICY_RUNTIME_FILE"

MODE_ENFORCE = "enforce"
MODE_LAUNCH_FREE = "launch_free"
MODE_DISABLED = "disabled"
VALID_MODES = frozenset({MODE_ENFORCE, MODE_LAUNCH_FREE, MODE_DISABLED})

AUDIENCE_PUBLIC = "public"
AUDIENCE_ACCOUNT = "account"
AUDIENCE_ENTITLED = "entitled"
AUDIENCE_DISABLED = "disabled"
VALID_AUDIENCES = frozenset({AUDIENCE_PUBLIC, AUDIENCE_ACCOUNT, AUDIENCE_ENTITLED, AUDIENCE_DISABLED})

BILLING_INHERIT = "inherit"
BILLING_FREE = "free"
BILLING_METERED = "metered"
BILLING_DISABLED = "disabled"
VALID_BILLING = frozenset({BILLING_INHERIT, BILLING_FREE, BILLING_METERED, BILLING_DISABLED})
MATERIAL_PRICING_MODES = frozenset({"by_pack", "by_material"})

DEFAULT_POLICY: dict[str, Any] = {
    "schema_version": POLICY_SCHEMA_VERSION,
    "policy_revision": "builtin-enforce-v1",
    "mode": MODE_ENFORCE,
    "audience": AUDIENCE_PUBLIC,
    "packs": {},
    "tools": {},
    "pricing": {"tools": {}},
    "rate_limits": {"surfaces": {}, "tools": {}},
    "facades": {"free": {"data_row_limit": 100}},
}

_CACHE_KEY: tuple[str, str, int | None, int | None] | None = None
_CACHE_VALUE: dict[str, Any] | None = None


class AccessPolicyError(ValueError):
    """Raised when an explicitly configured operator policy is invalid."""


def _normalized_id(value: Any) -> str:
    return str(value or "").strip().lower()


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def _validate_policy(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise AccessPolicyError("access policy must be a JSON object")
    policy = _deep_merge(DEFAULT_POLICY, raw)
    if str(policy.get("schema_version") or "") != POLICY_SCHEMA_VERSION:
        raise AccessPolicyError(f"access policy schema_version must be {POLICY_SCHEMA_VERSION}")
    if _normalized_id(policy.get("mode")) not in VALID_MODES:
        raise AccessPolicyError(f"access policy mode must be one of {sorted(VALID_MODES)}")
    if _normalized_id(policy.get("audience")) not in VALID_AUDIENCES:
        raise AccessPolicyError(f"access policy audience must be one of {sorted(VALID_AUDIENCES)}")
    if not str(policy.get("policy_revision") or "").strip():
        raise AccessPolicyError("access policy requires policy_revision")
    for collection in ("packs", "tools"):
        entries = policy.get(collection)
        if not isinstance(entries, dict):
            raise AccessPolicyError(f"access policy {collection} must be an object")
        for resource_id, entry in entries.items():
            if not isinstance(entry, dict):
                raise AccessPolicyError(f"access policy {collection}.{resource_id} must be an object")
            billing = _normalized_id(entry.get("billing", BILLING_INHERIT))
            audience = _normalized_id(entry.get("audience", policy["audience"]))
            if billing not in VALID_BILLING:
                raise AccessPolicyError(
                    f"access policy {collection}.{resource_id}.billing must be one of {sorted(VALID_BILLING)}"
                )
            if audience not in VALID_AUDIENCES:
                raise AccessPolicyError(
                    f"access policy {collection}.{resource_id}.audience must be one of {sorted(VALID_AUDIENCES)}"
                )
    pricing = policy.get("pricing") or {}
    if not isinstance(pricing, dict):
        raise AccessPolicyError("access policy pricing must be an object")
    price_tools = pricing.get("tools") or {}
    if not isinstance(price_tools, dict):
        raise AccessPolicyError("access policy pricing.tools must be an object")
    for tool_name, entry in price_tools.items():
        if not str(tool_name or "").strip() or not isinstance(entry, dict):
            raise AccessPolicyError("access policy pricing.tools entries require a tool name and object value")
        for field in ("base_micro_usd", "per_unit_micro_usd"):
            value = entry.get(field)
            if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
                raise AccessPolicyError(f"access policy pricing.tools.{tool_name}.{field} must be a non-negative integer")
        version = entry.get("pricing_version")
        if version is not None and (not isinstance(version, str) or not version.strip() or len(version) > 128):
            raise AccessPolicyError(f"access policy pricing.tools.{tool_name}.pricing_version must be 1-128 characters")
    facades = policy.get("facades")
    free = facades.get("free") if isinstance(facades, dict) else None
    row_limit = free.get("data_row_limit") if isinstance(free, dict) else None
    if isinstance(row_limit, bool) or not isinstance(row_limit, int) or not 1 <= row_limit <= 500:
        raise AccessPolicyError("access policy facades.free.data_row_limit must be an integer from 1 to 500")
    return policy


def _policy_cache_key() -> tuple[str, str, int | None, int | None]:
    inline = str(os.getenv(POLICY_JSON_ENV, "") or "").strip()
    configured_path = (
        str(os.getenv(POLICY_FILE_ENV, "") or "").strip()
        or str(os.getenv(RUNTIME_POLICY_FILE_ENV, "") or "").strip()
    )
    if inline or not configured_path:
        return inline, configured_path, None, None
    path = Path(configured_path)
    try:
        stat = path.stat()
        return inline, str(path.resolve()), stat.st_mtime_ns, stat.st_size
    except OSError:
        return inline, str(path), None, None


def load_access_policy() -> dict[str, Any]:
    """Load the external operator policy, re-reading a changed file automatically."""
    global _CACHE_KEY, _CACHE_VALUE
    key = _policy_cache_key()
    if key == _CACHE_KEY and _CACHE_VALUE is not None:
        return copy.deepcopy(_CACHE_VALUE)

    inline, configured_path, _mtime, _size = key
    if inline:
        try:
            raw = json.loads(inline)
        except json.JSONDecodeError as exc:
            raise AccessPolicyError(f"{POLICY_JSON_ENV} is not valid JSON: {exc}") from exc
    elif configured_path:
        path = Path(configured_path)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except OSError as exc:
            # The dashboard-managed runtime file is optional until its first
            # activation. An explicitly authored deployment file is not.
            authored_path = str(os.getenv(POLICY_FILE_ENV, "") or "").strip()
            if not authored_path and not path.exists():
                raw = DEFAULT_POLICY
            else:
                raise AccessPolicyError(f"cannot read access policy {path}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise AccessPolicyError(f"access policy {path} is not valid JSON: {exc}") from exc
    else:
        raw = DEFAULT_POLICY

    policy = _validate_policy(raw)
    _CACHE_KEY = key
    _CACHE_VALUE = policy
    return copy.deepcopy(policy)


def clear_access_policy_cache() -> None:
    global _CACHE_KEY, _CACHE_VALUE
    _CACHE_KEY = None
    _CACHE_VALUE = None


def validate_access_policy(policy: Any) -> dict[str, Any]:
    """Public validator used by the operator control-plane endpoint."""
    return _validate_policy(policy)


def activate_access_policy(policy: Any, path: str | Path) -> dict[str, Any]:
    """Validate and atomically materialize one active runtime policy."""
    normalized = _validate_policy(policy)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(normalized, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, target)
    finally:
        try:
            Path(tmp_name).unlink(missing_ok=True)
        except OSError:
            pass
    clear_access_policy_cache()
    return load_access_policy()


def policy_fingerprint(policy: dict[str, Any] | None = None) -> str:
    payload = policy or load_access_policy()
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _resource_override(policy: dict[str, Any], resource_kind: str, resource_id: str) -> dict[str, Any]:
    collection = "packs" if _normalized_id(resource_kind) in {"pack", "data_pack"} else "tools"
    entries = policy.get(collection) if isinstance(policy.get(collection), dict) else {}
    wildcard = entries.get("*") if isinstance(entries.get("*"), dict) else {}
    # A scoped id such as ``resolve_point:usa`` inherits the tool-wide rule and
    # can then refine it. This keeps country bundles independently switchable
    # without duplicating the complete tool policy for every country.
    parent_id = resource_id.split(":", 1)[0]
    parent = entries.get(parent_id) if isinstance(entries.get(parent_id), dict) else {}
    exact = entries.get(resource_id) if isinstance(entries.get(resource_id), dict) else {}
    return _deep_merge(_deep_merge(wildcard, parent), exact)


def _commercial_eligible(permissions: Iterable[Any] | None) -> bool:
    values = {_normalized_id(value) for value in (permissions or ()) if _normalized_id(value)}
    return values == {"paid"}


def resolve_effective_access(
    *,
    resource_kind: str,
    resource_id: str,
    authored_pricing: str = "free",
    license_permissions: Iterable[Any] | None = None,
    publication_cleared: bool = True,
    caller_authenticated: bool = False,
    caller_entitled: bool = False,
    local_installed: bool = False,
    trusted_artifact: bool = False,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return one auditable access/billing decision for a pack or tool."""
    active = _validate_policy(policy) if policy is not None else load_access_policy()
    rid = _normalized_id(resource_id)
    override = _resource_override(active, resource_kind, rid)
    mode = _normalized_id(active.get("mode"))
    audience = _normalized_id(override.get("audience", active.get("audience")))
    billing = _normalized_id(override.get("billing", BILLING_INHERIT))
    normalized_pricing = str(authored_pricing or "free").strip().lower()
    product_metered = normalized_pricing.startswith("paid") or normalized_pricing in MATERIAL_PRICING_MODES
    if billing == BILLING_FREE:
        product_metered = False
    elif billing == BILLING_METERED:
        product_metered = True

    commercial_eligible = _commercial_eligible(license_permissions)
    explicit_internal = bool(local_installed or trusted_artifact)
    reasons: list[str] = []
    allow = True

    if mode == MODE_DISABLED or billing == BILLING_DISABLED or audience == AUDIENCE_DISABLED:
        allow = False
        reasons.append("operator_disabled")
    if not publication_cleared and not explicit_internal:
        allow = False
        reasons.append("publication_not_cleared")
    if audience == AUDIENCE_ACCOUNT and not caller_authenticated and not explicit_internal:
        allow = False
        reasons.append("account_required")
    if audience == AUDIENCE_ENTITLED and not caller_entitled and not explicit_internal:
        allow = False
        reasons.append("entitlement_required")

    forced_free = bool(product_metered and not commercial_eligible)
    if forced_free:
        reasons.append("licence_blocks_paid_lane")

    settlement_required = bool(
        allow
        and product_metered
        and commercial_eligible
        and mode == MODE_ENFORCE
        and not explicit_internal
    )
    if explicit_internal:
        access_lane = "local_installed" if local_installed else "trusted_artifact"
    elif not allow:
        access_lane = "blocked"
    elif settlement_required:
        access_lane = "metered"
    elif mode == MODE_LAUNCH_FREE and product_metered and commercial_eligible:
        access_lane = "launch_free"
        reasons.append("settlement_waived_by_operator")
    else:
        access_lane = "free"

    return {
        "schema_version": POLICY_SCHEMA_VERSION,
        "policy_revision": str(active.get("policy_revision")),
        "policy_fingerprint": policy_fingerprint(active),
        "resource_kind": _normalized_id(resource_kind),
        "resource_id": rid,
        "allow": allow,
        "reason_codes": reasons or ["allowed"],
        "access_lane": access_lane,
        "audience": audience,
        "operator_mode": mode,
        "authored_pricing": str(authored_pricing or "free"),
        "billing_override": billing,
        "commercial_eligible": commercial_eligible,
        "publication_cleared": bool(publication_cleared),
        "settlement_required": settlement_required,
        "payment_required": settlement_required,
        "usage_gates_required": not explicit_internal,
    }


def _positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def free_facade_data_row_limit() -> int:
    return int(load_access_policy()["facades"]["free"]["data_row_limit"])


def surface_rate_limit(
    surface: str,
    *,
    default_limit: int,
    default_window_seconds: int,
    tier: str | None = None,
) -> tuple[int, int]:
    policy = load_access_policy()
    rate_limits = policy.get("rate_limits") if isinstance(policy.get("rate_limits"), dict) else {}
    surfaces = rate_limits.get("surfaces") if isinstance(rate_limits.get("surfaces"), dict) else {}
    override = surfaces.get(_normalized_id(surface)) if isinstance(surfaces.get(_normalized_id(surface)), dict) else {}
    tier_override = (
        override.get(_normalized_id(tier))
        if tier and isinstance(override.get(_normalized_id(tier)), dict)
        else {}
    )
    merged = _deep_merge(override, tier_override)
    return (
        _positive_int(merged.get("limit")) or int(default_limit),
        _positive_int(merged.get("window_seconds")) or int(default_window_seconds),
    )


def tool_rate_limit(
    tool_name: str,
    tier: str,
    *,
    default_limit: int,
    default_window_seconds: int,
) -> tuple[int, int]:
    policy = load_access_policy()
    rate_limits = policy.get("rate_limits") if isinstance(policy.get("rate_limits"), dict) else {}
    tools = rate_limits.get("tools") if isinstance(rate_limits.get("tools"), dict) else {}
    tool = tools.get(_normalized_id(tool_name)) if isinstance(tools.get(_normalized_id(tool_name)), dict) else {}
    tier_override = tool.get(_normalized_id(tier)) if isinstance(tool.get(_normalized_id(tier)), dict) else {}
    merged = _deep_merge(tool, tier_override)
    return (
        _positive_int(merged.get("limit")) or int(default_limit),
        _positive_int(merged.get("window_seconds")) or int(default_window_seconds),
    )
