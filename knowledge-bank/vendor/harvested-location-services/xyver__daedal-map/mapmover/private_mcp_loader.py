from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from types import ModuleType


DEFAULT_PRIVATE_MCP_BUNDLE_ROOTS = (
    Path("/app/private_mcp_tools"),
    Path("/app/county-map-private/tools"),
)

_PROVIDER_CACHE: dict[str, ModuleType] = {}
_SCAN_COMPLETE = False


def clear_private_mcp_provider_cache() -> None:
    global _SCAN_COMPLETE
    _PROVIDER_CACHE.clear()
    _SCAN_COMPLETE = False


def get_private_mcp_provider(provider_slug: str) -> ModuleType | None:
    _scan_private_mcp_bundle_roots()
    return _PROVIDER_CACHE.get(str(provider_slug or "").strip().lower())


def _scan_private_mcp_bundle_roots() -> None:
    global _SCAN_COMPLETE
    if _SCAN_COMPLETE:
        return

    for root in _configured_bundle_roots():
        if not root.exists():
            continue
        for bundle_path in _bundle_paths_for_root(root):
            module = _load_bundle_module(bundle_path)
            if module is None:
                continue
            provider_slug = str(getattr(module, "PROVIDER_SLUG", "") or "").strip().lower()
            if not provider_slug:
                continue
            _PROVIDER_CACHE[provider_slug] = module

    _SCAN_COMPLETE = True


def _configured_bundle_roots() -> list[Path]:
    configured: list[Path] = []
    raw = str(os.getenv("PRIVATE_MCP_BUNDLE_ROOTS", "")).strip()
    if raw:
        for item in raw.split(os.pathsep):
            candidate = str(item or "").strip()
            if candidate:
                configured.append(Path(candidate))
    configured.extend(DEFAULT_PRIVATE_MCP_BUNDLE_ROOTS)

    deduped: list[Path] = []
    seen: set[str] = set()
    for path in configured:
        key = str(path.resolve()) if path.exists() else str(path)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(path)
    return deduped


def _load_bundle_module(bundle_path: Path) -> ModuleType | None:
    module_name = f"private_mcp_bundle_{bundle_path.parent.name}"
    spec = importlib.util.spec_from_file_location(module_name, bundle_path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _bundle_paths_for_root(root: Path) -> list[Path]:
    if root.is_file():
        return [root] if root.name == "private_mcp_bundle.py" else []
    if not root.is_dir():
        return []

    bundle_paths: list[Path] = []
    direct_bundle = root / "private_mcp_bundle.py"
    if direct_bundle.exists():
        bundle_paths.append(direct_bundle)
    bundle_paths.extend(root.glob("*/private_mcp_bundle.py"))

    deduped: list[Path] = []
    seen: set[str] = set()
    for bundle_path in bundle_paths:
        key = str(bundle_path.resolve())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(bundle_path)
    return deduped
