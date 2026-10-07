"""Runtime reader for generated data/geometry material-policy envelopes.

Catalog generation owns legal interpretation. Hosted runtimes only consume
the generated decision, so they cannot independently reinterpret a licence
label. A missing ``material_policy`` fails closed.
"""

from __future__ import annotations

from typing import Any, Iterable


def _clean(value: Any) -> str:
    return str(value or "").strip().lower()


def material_access_facts(record: dict[str, Any] | None) -> dict[str, Any]:
    """Return one normalized legal/access decision without mapping labels."""
    record = record if isinstance(record, dict) else {}
    policy = record.get("material_policy")
    if isinstance(policy, dict):
        hosted = policy.get("hosted_access") if isinstance(policy.get("hosted_access"), dict) else {}
        redistribution = policy.get("redistribution") if isinstance(policy.get("redistribution"), dict) else {}
        surfaces = policy.get("surface_access") if isinstance(policy.get("surface_access"), dict) else {}
        surface_access = {
            "hosted_results": bool(surfaces.get("hosted_results", hosted.get("free_allowed"))),
            "server_rendered_display": bool(surfaces.get("server_rendered_display", hosted.get("free_allowed"))),
            "client_geometry": bool(surfaces.get("client_geometry", redistribution.get("allowed"))),
            "download": bool(surfaces.get("download", redistribution.get("allowed"))),
        }
        return {
            "permission": _clean(policy.get("permission")) or None,
            "publication_cleared": bool(hosted.get("publication_ready")),
            "free_hosted_allowed": bool(hosted.get("free_allowed")),
            "paid_hosted_allowed": bool(hosted.get("paid_allowed")),
            "maximum_hosted_lane": _clean(hosted.get("maximum_lane")) or "blocked",
            "redistribution": _clean(redistribution.get("status")) or "unknown",
            "redistribution_allowed": bool(redistribution.get("allowed")),
            "surface_access": surface_access,
            "attribution": dict(policy.get("attribution") or {}),
            "citation": dict(policy.get("citation") or {}),
            "reason_codes": list(hosted.get("reason_codes") or []),
            "policy_fingerprint": policy.get("policy_fingerprint"),
            "source": "material_policy",
        }

    return {
        "permission": None,
        "publication_cleared": False,
        "free_hosted_allowed": False,
        "paid_hosted_allowed": False,
        "maximum_hosted_lane": "blocked",
        "redistribution": "unknown",
        "redistribution_allowed": False,
        "surface_access": {
            "hosted_results": False,
            "server_rendered_display": False,
            "client_geometry": False,
            "download": False,
        },
        "attribution": {},
        "citation": {},
        "reason_codes": ["material_policy_missing"],
        "policy_fingerprint": None,
        "source": "missing",
    }


def combine_material_access(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Take the strictest generated decision across contributing material."""
    facts = [material_access_facts(record) for record in records if isinstance(record, dict)]
    permissions = {fact["permission"] for fact in facts if fact.get("permission")}
    all_published = bool(facts) and all(fact["publication_cleared"] for fact in facts)
    all_free = bool(facts) and all(fact["free_hosted_allowed"] for fact in facts)
    all_paid = bool(facts) and all(fact["paid_hosted_allowed"] for fact in facts)
    all_redistributable = bool(facts) and all(fact["redistribution_allowed"] for fact in facts)
    surfaces = ("hosted_results", "server_rendered_display", "client_geometry", "download")
    return {
        "permissions": permissions,
        "publication_cleared": all_published,
        "free_hosted_allowed": all_free,
        "paid_hosted_allowed": all_paid,
        "maximum_hosted_lane": "paid" if all_paid else "free" if all_free else "blocked",
        "redistribution_allowed": all_redistributable,
        "surface_access": {
            surface: bool(facts) and all(fact["surface_access"].get(surface) for fact in facts)
            for surface in surfaces
        },
        "members": facts,
    }
