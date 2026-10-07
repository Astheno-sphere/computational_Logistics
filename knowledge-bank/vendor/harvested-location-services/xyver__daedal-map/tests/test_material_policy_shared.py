from __future__ import annotations

from material_policy_shared import combine_material_access, material_access_facts


def _policy(*, lane: str, published: bool = True, redistribution: bool = True) -> dict:
    return {
        "material_policy": {
            "permission": "paid" if lane == "paid" else "free",
            "hosted_access": {
                "maximum_lane": lane,
                "publication_ready": published,
                "free_allowed": published and lane in {"free", "paid"},
                "paid_allowed": published and lane == "paid",
                "reason_codes": ["allowed"] if published else ["publication_not_cleared"],
            },
            "redistribution": {
                "status": "allowed" if redistribution else "restricted",
                "allowed": published and redistribution,
            },
            "surface_access": {
                "hosted_results": published,
                "server_rendered_display": published,
                "client_geometry": published and redistribution,
                "download": published and redistribution,
            },
            "attribution": {"status": "resolved", "lines": []},
            "citation": {"entries": []},
            "policy_fingerprint": "abc123",
        }
    }


def test_reads_generated_material_policy_without_reinterpreting_license() -> None:
    facts = material_access_facts(_policy(lane="paid"))

    assert facts["source"] == "material_policy"
    assert facts["permission"] == "paid"
    assert facts["paid_hosted_allowed"] is True
    assert facts["redistribution_allowed"] is True
    assert facts["surface_access"]["client_geometry"] is True


def test_combination_uses_strictest_contributing_material() -> None:
    combined = combine_material_access([_policy(lane="paid"), _policy(lane="free")])

    assert combined["publication_cleared"] is True
    assert combined["free_hosted_allowed"] is True
    assert combined["paid_hosted_allowed"] is False
    assert combined["maximum_hosted_lane"] == "free"
    assert combined["surface_access"]["hosted_results"] is True


def test_redistribution_is_independent_from_hosted_service_permission() -> None:
    facts = material_access_facts(_policy(lane="paid", redistribution=False))

    assert facts["paid_hosted_allowed"] is True
    assert facts["redistribution_allowed"] is False
    assert facts["surface_access"]["client_geometry"] is False
    assert facts["surface_access"]["hosted_results"] is True


def test_legacy_projection_is_not_accepted_without_material_policy() -> None:
    facts = material_access_facts(
        {
            "permission": "paid",
            "source_licenses": [
                {"permission": "paid", "license_review_status": "approved"},
                {"permission": "paid", "license_review_status": "needs_review"},
            ],
        }
    )

    assert facts["source"] == "missing"
    assert facts["permission"] is None
    assert facts["reason_codes"] == ["material_policy_missing"]
    assert facts["publication_cleared"] is False
    assert facts["paid_hosted_allowed"] is False


def test_public_geometry_projection_keeps_compact_license_and_citation_contract() -> None:
    from geometry_catalog_shared import build_published_geometry_catalog

    policy = _policy(lane="paid")["material_policy"]
    policy["licenses"] = ["CC BY 4.0"]
    policy["license_evidence"] = [{"license": "CC BY 4.0", "source_url": "https://example.test"}]
    policy["provenance"] = {"large": "private receipt detail"}
    policy["object_license_policy"] = {"large": "repeated crosswalk detail"}
    catalog = {
        "geometry_banks": [{"bank_id": "example", "material_policy": policy}],
        "geometry_products": [],
    }

    public = build_published_geometry_catalog(catalog)
    public_policy = public["geometry_banks"][0]["material_policy"]
    assert public_policy["licenses"] == ["CC BY 4.0"]
    assert public_policy["hosted_access"]["maximum_lane"] == "paid"
    assert "citation" in public_policy
    assert "license_evidence" in public_policy
    assert "provenance" not in public_policy
    assert "object_license_policy" not in public_policy
