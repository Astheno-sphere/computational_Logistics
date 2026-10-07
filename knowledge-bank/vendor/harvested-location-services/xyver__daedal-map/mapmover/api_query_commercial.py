from __future__ import annotations

import base64
import json
import os
from typing import Any
from urllib.parse import urljoin

import requests
from fastapi import Request
from fastapi.responses import JSONResponse, Response

from access_policy_shared import resolve_effective_access
from pack_registry_shared import pack_profile
from mapmover.paths import SITE_URL
from mapmover.artifact_access import (
    artifact_token_records,
    get_artifact_token_record,
)


COMMERCIAL_ACCESS_CHECK_PATH = "/internal/commercial-access/check"
COMMERCIAL_ACCESS_SETTLE_PATH = "/internal/commercial-access/settle"
COMMERCIAL_ACCESS_TIMEOUT_SECONDS = 10.0
COMMERCIAL_ACCESS_FORWARDED_HEADERS = {
    "accept",
    "authorization",
    "payment-required",
    "payment-response",
    "payment-signature",
    "user-agent",
    "x-payment",
    "x-payment-response",
}
def commercial_access_enabled() -> bool:
    return str(os.getenv("COMMERCIAL_ACCESS_ENABLED", "")).strip().lower() in {"1", "true", "yes", "on"}


def trusted_artifact_tokens() -> set[str]:
    return {record.token for record in artifact_token_records()}


def get_trusted_artifact_token(request: Request) -> str | None:
    record = get_artifact_token_record(request)
    return record.token if record is not None else None


def pack_effective_access(
    pack_id: str | None,
    *,
    license_permissions=None,
    publication_cleared: bool = True,
    caller_authenticated: bool = False,
    caller_entitled: bool = False,
    local_installed: bool = False,
    trusted_artifact: bool = False,
) -> dict[str, Any]:
    normalized = str(pack_id or "").strip().lower()
    from mapmover.data_loading import get_pack_metadata, load_catalog

    pack = get_pack_metadata(normalized, load_catalog())
    if not isinstance(pack, dict):
        return resolve_effective_access(
            resource_kind="pack",
            resource_id=normalized,
            authored_pricing="free",
            license_permissions=set(),
            publication_cleared=False,
            caller_authenticated=caller_authenticated,
            caller_entitled=caller_entitled,
            local_installed=local_installed,
            trusted_artifact=trusted_artifact,
        )
    material_policy = pack.get("material_policy") if isinstance(pack.get("material_policy"), dict) else {}
    hosted_access = material_policy.get("hosted_access") if isinstance(material_policy.get("hosted_access"), dict) else {}
    catalog_permission = str(material_policy.get("permission") or hosted_access.get("maximum_lane") or "").strip().lower()
    # The registry owns the product's authored free/paid classification. The
    # material permission is a separate legal ceiling: free-only material can
    # force a paid product onto a free lane, but paid-eligible material must not
    # turn a product authored as free into a metered one.
    authored_pricing = str(pack_profile(normalized).get("pricing") or "free")
    permissions = ({catalog_permission} if catalog_permission else set()) if license_permissions is None else license_permissions
    publication_cleared = bool(hosted_access.get("publication_ready", False))
    return resolve_effective_access(
        resource_kind="pack",
        resource_id=normalized,
        authored_pricing=authored_pricing,
        license_permissions=permissions,
        publication_cleared=publication_cleared,
        caller_authenticated=caller_authenticated,
        caller_entitled=caller_entitled,
        local_installed=local_installed,
        trusted_artifact=trusted_artifact,
    )


def pack_requires_commercial_access(
    pack_id: str | None,
    *,
    license_permissions=None,
    publication_cleared: bool = True,
) -> bool:
    """Return the effective settlement requirement for one hosted pack.

    The shared pack registry owns authored pricing. ``catalog.json`` supplies
    the material ceiling that may force the request free or block publication;
    temporary operator overrides remain separate access-policy decisions.
    """
    normalized = str(pack_id or "").strip().lower()
    if not normalized:
        return False
    return bool(pack_effective_access(
        normalized,
        license_permissions=license_permissions,
        publication_cleared=publication_cleared,
    )["settlement_required"])


def commercial_access_timeout_seconds() -> float:
    raw_value = str(os.getenv("COMMERCIAL_ACCESS_TIMEOUT_SECONDS", "")).strip()
    if not raw_value:
        return COMMERCIAL_ACCESS_TIMEOUT_SECONDS
    try:
        return max(1.0, float(raw_value))
    except ValueError:
        return COMMERCIAL_ACCESS_TIMEOUT_SECONDS


def commercial_access_base_url() -> str:
    configured = str(os.getenv("COMMERCIAL_ACCESS_VERIFIER_BASE_URL", "")).strip().rstrip("/")
    return configured or SITE_URL.rstrip("/")


def commercial_access_internal_token() -> str:
    return str(os.getenv("CLOUD_INTERNAL_API_TOKEN", "")).strip()


def forwarded_commercial_headers(request: Request) -> dict[str, str]:
    forwarded: dict[str, str] = {}
    for header_name in COMMERCIAL_ACCESS_FORWARDED_HEADERS:
        raw_value = request.headers.get(header_name)
        if raw_value is not None and str(raw_value).strip():
            forwarded[header_name] = str(raw_value).strip()
    return forwarded


def post_commercial_access(path: str, payload: dict[str, Any]) -> tuple[int, dict[str, Any] | None]:
    url = urljoin(f"{commercial_access_base_url()}/", path.lstrip("/"))
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    token = commercial_access_internal_token()
    if token:
        headers["x-internal-api-key"] = token
    response = requests.post(
        url,
        json=payload,
        headers=headers,
        timeout=commercial_access_timeout_seconds(),
    )
    try:
        body = response.json()
    except Exception:
        body = None
    return response.status_code, body


def commercial_access_response(
    request_id: str | None,
    verifier_payload: dict[str, Any] | None,
    *,
    pack_id: str | None = None,
    source_id: str | None = None,
) -> Response:
    def discovery_payload(pricing: dict[str, Any] | None = None) -> dict[str, Any]:
        site_url = str(SITE_URL or "https://daedalmap.com").rstrip("/")
        payload: dict[str, Any] = {
            "docs_url": f"{site_url}/agents",
            "examples_url": f"{site_url}/docs/agent-examples",
            "catalog_url": "https://app.daedalmap.com/api/v1/catalog",
            "guide_url": "https://app.daedalmap.com/api/v1/guide",
            "first_steps": [
                "GET /api/v1/catalog",
                f"GET /api/v1/packs/{pack_id or 'earthquakes'}",
                "Retry this same paid call only after inspecting the free pack detail.",
            ],
        }
        if pack_id:
            payload["pack_id"] = pack_id
            payload["pack_url"] = f"https://app.daedalmap.com/api/v1/packs/{pack_id}"
            payload["public_pack_url"] = f"{site_url}/packs/{pack_id}"
        if source_id:
            payload["source_id"] = source_id
        if isinstance(pricing, dict):
            suggestions = pricing.get("suggestions") or []
            if isinstance(suggestions, list) and suggestions:
                payload["narrowing_suggestions"] = [str(item) for item in suggestions[:5] if str(item).strip()]
        return payload

    def pricing_payload(pricing: dict[str, Any] | None = None) -> dict[str, Any]:
        pricing = pricing if isinstance(pricing, dict) else {}
        return {
            "message": "Small queries stay cheap; broad scans cost more or need narrower filters.",
            "price_display": pricing.get("price_display"),
            "scope_class": pricing.get("scope_class"),
            "soft_cap_usd": pricing.get("soft_cap_usd"),
            "suggestions": pricing.get("suggestions") or [],
        }

    def augment_payment_required_header(
        header_value: str,
        *,
        pricing: dict[str, Any] | None = None,
    ) -> str:
        raw = str(header_value or "").strip()
        if not raw:
            return raw
        try:
            decoded = base64.b64decode(raw).decode("utf-8")
            challenge_payload = json.loads(decoded)
        except Exception:
            return raw
        if not isinstance(challenge_payload, dict):
            return raw

        resource = challenge_payload.get("resource")
        if isinstance(resource, dict):
            if pack_id and source_id:
                resource["description"] = (
                    f"DaedalMap paid dataset query for pack '{pack_id}' and source '{source_id}'. "
                    "Use the free catalog and pack detail endpoints first, then retry this call with payment."
                )
            elif pack_id:
                resource["description"] = (
                    f"DaedalMap paid dataset query for pack '{pack_id}'. "
                    "Use the free catalog and pack detail endpoints first, then retry this call with payment."
                )

        extensions = challenge_payload.get("extensions")
        if not isinstance(extensions, dict):
            extensions = {}
            challenge_payload["extensions"] = extensions
        extensions["daedalmap"] = {
            "discovery": discovery_payload(pricing),
            "pricing": pricing_payload(pricing),
        }
        try:
            encoded = base64.b64encode(
                json.dumps(challenge_payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
            ).decode("ascii")
            return encoded
        except Exception:
            return raw

    payload = verifier_payload or {}
    challenge = payload.get("challenge") if isinstance(payload, dict) else None
    headers = {}
    body = None
    context = payload.get("context") if isinstance(payload, dict) else None
    pricing = context.get("pricing") if isinstance(context, dict) else None
    if isinstance(challenge, dict):
        raw_headers = challenge.get("headers") or {}
        if isinstance(raw_headers, dict):
            headers = {
                str(key): str(value)
                for key, value in raw_headers.items()
                if str(key).strip() and value is not None
            }
        body = challenge.get("body")
    payment_required_header = headers.get("payment-required") or headers.get("Payment-Required")
    if payment_required_header:
        enriched = augment_payment_required_header(payment_required_header, pricing=pricing)
        headers["payment-required"] = enriched
        if "Payment-Required" in headers:
            headers["Payment-Required"] = enriched

    status_code = int(payload.get("http_status") or 402)
    if isinstance(body, dict):
        response_body = dict(body)
        if isinstance(pricing, dict):
            response_body.setdefault("daedalmap_pricing", pricing_payload(pricing))
        response_body.setdefault("daedalmap_discovery", discovery_payload(pricing))
        response = JSONResponse(response_body, status_code=status_code)
    elif isinstance(body, list):
        response = JSONResponse(body, status_code=status_code)
    elif isinstance(body, str) and body.strip():
        response = Response(content=body, status_code=status_code, media_type="application/json")
    else:
        fallback_body = {
            "request_id": request_id,
            "payment_required": True,
            "error": {
                "code": str(payload.get("code") or "commercial_access_required"),
                "message": str(payload.get("message") or "Commercial access is required for this capability."),
                "retry_hint": "Use the free catalog and pack detail endpoints first, then retry this exact paid call with payment.",
            },
            "daedalmap_discovery": discovery_payload(pricing),
            "daedalmap_pricing": pricing_payload(pricing),
        }
        response = JSONResponse(fallback_body, status_code=status_code)
    for key, value in headers.items():
        response.headers[key] = value
    return response


def settle_commercial_access(
    request_id: str,
    settlement_id: str,
    *,
    success: bool,
    request_fingerprint: str | None = None,
    caller_binding: str | None = None,
    actual_pricing: dict[str, Any] | None = None,
    meter_receipt: dict[str, Any] | None = None,
) -> tuple[bool, dict[str, Any] | None]:
    _status_code, payload = post_commercial_access(
        COMMERCIAL_ACCESS_SETTLE_PATH,
        {
            "request_id": request_id,
            "settlement_id": settlement_id,
            "outcome": {
                "status": "success" if success else "failed",
                "actual_pricing": actual_pricing if isinstance(actual_pricing, dict) else None,
                "meter_receipt": meter_receipt if isinstance(meter_receipt, dict) else None,
            },
            "request_context": {"request_fingerprint": request_fingerprint} if request_fingerprint else {},
            "caller": {"caller_binding": caller_binding} if caller_binding else {},
        },
    )
    if isinstance(payload, dict) and str(payload.get("status") or "").strip().lower() == "allow":
        return True, payload
    return False, payload


def settlement_headers(payload: dict[str, Any] | None) -> dict[str, str]:
    settlement = (payload or {}).get("settlement") or {}
    raw_headers = settlement.get("headers") or {}
    if not isinstance(raw_headers, dict):
        return {}
    return {
        str(key): str(value)
        for key, value in raw_headers.items()
        if str(key).strip() and value is not None
    }


def pricing_amount_usdc_base_units(payload: dict[str, Any] | None) -> int | None:
    context = (payload or {}).get("context") or {}
    if not isinstance(context, dict):
        return None
    pricing = context.get("pricing") or {}
    if not isinstance(pricing, dict):
        return None
    raw_value = pricing.get("amount_usdc_base_units")
    if raw_value is None:
        return None
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return None
