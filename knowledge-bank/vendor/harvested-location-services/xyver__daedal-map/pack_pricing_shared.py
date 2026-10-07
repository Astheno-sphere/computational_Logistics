from __future__ import annotations

from pack_registry_shared import free_pack_ids, paid_pack_ids

# Derived pricing classification. The authored source of truth now lives in
# pack_registry_shared.py so new-pack updates only need one pricing edit.

FREE_PACK_IDS: frozenset[str] = frozenset(free_pack_ids())
PAID_PACK_IDS: frozenset[str] = frozenset(paid_pack_ids())
