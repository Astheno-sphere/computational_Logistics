"""
Canonical runtime path configuration for the public engine.

Runtime identity is intentionally small:
- `RUNTIME_MODE` controls the data plane (`local` or `cloud`)
- runtime code and frontend assets live under `APP_ROOT`
- writable state lives in explicit external directories
- `DATA_ROOT` is always the runtime-visible filesystem root for data access
"""

from __future__ import annotations

from pathlib import Path

from .runtime_config import APP_ROOT, STATIC_ROOT, TEMPLATES_ROOT, get_runtime_config
from .storage_mode import get_runtime_mode


def _as_path(value: str | Path) -> Path:
    return value if isinstance(value, Path) else Path(value)


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


_CONFIG = get_runtime_config()
_PATHS = _CONFIG["paths"]
_APP = _CONFIG["app"]

INSTALL_MODE = str(_CONFIG.get("install_mode", "local"))
RUNTIME_MODE = get_runtime_mode(_CONFIG.get("runtime_mode", "local"))

# Read-only app assets
STATIC_DIR = STATIC_ROOT
TEMPLATES_DIR = TEMPLATES_ROOT

# Writable runtime state
CONFIG_DIR = _as_path(_PATHS["config_dir"])
STATE_DIR = _as_path(_PATHS["state_dir"])
CACHE_DIR = _as_path(_PATHS["cache_dir"])
LOGS_DIR = _as_path(_PATHS["log_dir"])
PACKS_ROOT = _as_path(_PATHS["packs_root"])
RUNTIME_CONFIG_PATH = _as_path(_PATHS["runtime_config_path"])
SETTINGS_PATH = CONFIG_DIR / "settings.json"

# Data root
LOCAL_DATA_ROOT = _as_path(_PATHS["data_root"])
DATA_ROOT = LOCAL_DATA_ROOT

COUNTRIES_DIR = DATA_ROOT / "countries"
GLOBAL_DIR = DATA_ROOT / "global"
GEOMETRY_DIR = DATA_ROOT / "geometry"
COUNTRY_GEOMETRY_DIR = GEOMETRY_DIR / "countries"
CATALOG_PATH = DATA_ROOT / "catalog.json"
WIP_CATALOG_PATH = DATA_ROOT / "wip_catalog.json"
INDEX_PATH = DATA_ROOT / "index.json"

# App/network configuration
APP_HOST = str(_APP.get("host", "0.0.0.0"))
APP_PORT = int(_APP.get("port", 7000))
APP_URL = str(_APP.get("app_url", f"http://localhost:{APP_PORT}"))
SITE_URL = str(_APP.get("site_url", "http://localhost:8080"))
ACCOUNT_URL = f"{SITE_URL}/account"


def get_country_dir(iso3: str) -> Path:
    return COUNTRIES_DIR / iso3.upper()


def get_country_index(iso3: str) -> Path:
    return get_country_dir(iso3) / "index.json"


def get_country_geometry_dir(iso3: str) -> Path:
    return COUNTRY_GEOMETRY_DIR / iso3.upper()


def get_dataset_path(scope: str, dataset: str, filename: str = "events.parquet") -> Path:
    if scope.lower() == "global":
        return GLOBAL_DIR / dataset / filename
    return COUNTRIES_DIR / scope.upper() / dataset / filename


def get_geometry_path(geometry_type: str) -> Path:
    return GEOMETRY_DIR / f"{geometry_type}.parquet"


def validate_paths(verbose: bool = False) -> dict:
    paths_to_check = {
        "APP_ROOT": APP_ROOT,
        "CONFIG_DIR": CONFIG_DIR,
        "STATE_DIR": STATE_DIR,
        "CACHE_DIR": CACHE_DIR,
        "LOGS_DIR": LOGS_DIR,
        "PACKS_ROOT": PACKS_ROOT,
        "DATA_ROOT": DATA_ROOT,
        "CATALOG_PATH": CATALOG_PATH,
        "WIP_CATALOG_PATH": WIP_CATALOG_PATH,
        "INDEX_PATH": INDEX_PATH,
        "GEOMETRY_DIR": GEOMETRY_DIR,
    }

    results = {}
    for name, path in paths_to_check.items():
        exists = path.exists()
        results[name] = {"path": str(path), "exists": exists}
        if verbose:
            status = "OK" if exists else "MISSING"
            print(f"{status}: {name} = {path}")
    return results


if __name__ == "__main__":
    print("Runtime path configuration:")
    print("=" * 60)
    print(f"  INSTALL_MODE:        {INSTALL_MODE}")
    print(f"  RUNTIME_MODE:        {RUNTIME_MODE}")
    print(f"  APP_URL:             {APP_URL}")
    print(f"  SITE_URL:            {SITE_URL}")
    print(f"  DATA_ROOT:           {DATA_ROOT}")
    print(f"  PACKS_ROOT:          {PACKS_ROOT}")
    print(f"  RUNTIME_CONFIG_PATH: {RUNTIME_CONFIG_PATH}")
    print("=" * 60)
    validate_paths(verbose=True)
