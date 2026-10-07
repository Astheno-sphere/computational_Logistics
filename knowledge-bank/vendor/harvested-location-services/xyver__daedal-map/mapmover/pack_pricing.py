from __future__ import annotations

# Single source of truth for pack pricing classification.
# Default is FREE: only packs with an explicit paid pricing value in
# pack_registry_shared.py are gated by pack_requires_commercial_access().
# Full free<->paid switch checklist (enforcement, advertised pricing, license,
# public docs, and catalog surfaces):
# county-map-private/docs/future/API/mcp_publishing.md section 15.
from pack_pricing_shared import FREE_PACK_IDS, PAID_PACK_IDS
