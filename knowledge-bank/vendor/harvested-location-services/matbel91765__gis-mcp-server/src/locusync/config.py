"""Configuration management for LocuSync Server."""

import os
from dataclasses import dataclass, field


@dataclass
class NominatimConfig:
    """Configuration for Nominatim geocoding service."""

    base_url: str = "https://nominatim.openstreetmap.org"
    user_agent: str = "locusync-server/1.0.0"
    timeout: float = 10.0
    rate_limit_delay: float = 1.0  # Nominatim requires 1 req/sec max


@dataclass
class OSRMConfig:
    """Configuration for OSRM routing service."""

    base_url: str = "https://router.project-osrm.org"
    timeout: float = 30.0
    profile: str = "driving"  # driving, walking, cycling


@dataclass
class ValhallaConfig:
    """Configuration for Valhalla routing service (alternative)."""

    base_url: str = ""  # No public demo, must be self-hosted
    timeout: float = 30.0
    api_key: str = ""


@dataclass
class PeliasConfig:
    """Configuration for Pelias geocoding service."""

    base_url: str = ""  # Must be self-hosted or use a provider
    api_key: str = ""  # Optional, depends on provider
    timeout: float = 10.0


@dataclass
class OpenElevationConfig:
    """Configuration for Open-Elevation API service."""

    base_url: str = "https://api.open-elevation.com"
    timeout: float = 30.0


@dataclass
class CacheConfig:
    """Configuration for the result cache."""

    enabled: bool = True
    ttl: float = 86400.0  # 24h — geocoding/routing/elevation are stable
    maxsize: int = 2048
    # Optional Redis URL for a shared/persistent cache (falls back to in-process
    # when empty or when the redis package is unavailable).
    redis_url: str = ""


@dataclass
class ServerConfig:
    """Runtime/transport configuration for the MCP server."""

    transport: str = "stdio"  # stdio | http | sse
    host: str = "0.0.0.0"
    port: int = 8000
    # Optional bearer token. When set (HTTP/SSE), unauthenticated calls are rejected.
    auth_token: str = ""


@dataclass
class Config:
    """Main configuration for LocuSync Server."""

    nominatim: NominatimConfig = field(default_factory=NominatimConfig)
    osrm: OSRMConfig = field(default_factory=OSRMConfig)
    valhalla: ValhallaConfig = field(default_factory=ValhallaConfig)
    pelias: PeliasConfig = field(default_factory=PeliasConfig)
    open_elevation: OpenElevationConfig = field(default_factory=OpenElevationConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    server: ServerConfig = field(default_factory=ServerConfig)

    # General settings
    default_crs: str = "EPSG:4326"  # WGS84
    max_file_size_mb: int = 100
    temp_dir: str = "/tmp/locusync"
    # Sandbox root for file-I/O tools. read_file/write_file cannot escape it.
    workdir: str = "/tmp/locusync"
    # Hard cap on feature count for in-memory geometry operations (DoS guard).
    max_features: int = 50000
    # Above this many features, results are written to a file (handle + sample
    # returned) instead of inlined, to protect the LLM context window.
    max_inline_features: int = 1000
    # Optional PostGIS DSN (postgresql://...) enabling the SQL spatial tools.
    postgis_dsn: str = ""

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        config = cls()

        # Nominatim overrides
        if url := os.getenv("NOMINATIM_URL"):
            config.nominatim.base_url = url
        if user_agent := os.getenv("NOMINATIM_USER_AGENT"):
            config.nominatim.user_agent = user_agent

        # OSRM overrides
        if url := os.getenv("OSRM_URL"):
            config.osrm.base_url = url
        if profile := os.getenv("OSRM_PROFILE"):
            config.osrm.profile = profile

        # Valhalla overrides
        if url := os.getenv("VALHALLA_URL"):
            config.valhalla.base_url = url
        if api_key := os.getenv("VALHALLA_API_KEY"):
            config.valhalla.api_key = api_key

        # Pelias overrides
        if url := os.getenv("PELIAS_URL"):
            config.pelias.base_url = url
        if api_key := os.getenv("PELIAS_API_KEY"):
            config.pelias.api_key = api_key

        # Open-Elevation overrides
        if url := os.getenv("OPEN_ELEVATION_URL"):
            config.open_elevation.base_url = url

        # General overrides
        if crs := os.getenv("GIS_DEFAULT_CRS"):
            config.default_crs = crs
        if temp_dir := os.getenv("GIS_TEMP_DIR"):
            config.temp_dir = temp_dir
            config.workdir = temp_dir
        if workdir := os.getenv("LOCUSYNC_WORKDIR"):
            config.workdir = workdir
        if max_features := os.getenv("LOCUSYNC_MAX_FEATURES"):
            config.max_features = int(max_features)
        if max_inline := os.getenv("LOCUSYNC_MAX_INLINE_FEATURES"):
            config.max_inline_features = int(max_inline)
        if postgis_dsn := os.getenv("POSTGIS_DSN"):
            config.postgis_dsn = postgis_dsn

        # Cache overrides
        if (enabled := os.getenv("LOCUSYNC_CACHE_ENABLED")) is not None:
            config.cache.enabled = enabled.strip().lower() in ("1", "true", "yes", "on")
        if ttl := os.getenv("LOCUSYNC_CACHE_TTL"):
            config.cache.ttl = float(ttl)
        if maxsize := os.getenv("LOCUSYNC_CACHE_MAXSIZE"):
            config.cache.maxsize = int(maxsize)
        if redis_url := os.getenv("LOCUSYNC_REDIS_URL"):
            config.cache.redis_url = redis_url

        # Server/transport overrides
        if transport := os.getenv("LOCUSYNC_TRANSPORT"):
            config.server.transport = transport.strip().lower()
        if host := os.getenv("LOCUSYNC_HOST"):
            config.server.host = host
        if port := os.getenv("LOCUSYNC_PORT"):
            config.server.port = int(port)
        if token := os.getenv("LOCUSYNC_AUTH_TOKEN"):
            config.server.auth_token = token

        return config


# Global config instance
_config: Config | None = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = Config.from_env()
    return _config


def set_config(config: Config) -> None:
    """Set the global configuration instance."""
    global _config
    _config = config
