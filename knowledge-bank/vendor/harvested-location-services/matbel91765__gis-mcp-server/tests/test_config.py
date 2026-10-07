"""Tests for configuration management."""

import os
from unittest.mock import patch

from locusync.config import (
    Config,
    NominatimConfig,
    OSRMConfig,
    ValhallaConfig,
    get_config,
    set_config,
)


class TestNominatimConfig:
    """Tests for Nominatim configuration."""

    def test_default_values(self):
        """Test default configuration values."""
        config = NominatimConfig()
        assert config.base_url == "https://nominatim.openstreetmap.org"
        assert config.user_agent == "locusync-server/1.0.0"
        assert config.timeout == 10.0
        assert config.rate_limit_delay == 1.0


class TestOSRMConfig:
    """Tests for OSRM configuration."""

    def test_default_values(self):
        """Test default configuration values."""
        config = OSRMConfig()
        assert config.base_url == "https://router.project-osrm.org"
        assert config.timeout == 30.0
        assert config.profile == "driving"


class TestValhallaConfig:
    """Tests for Valhalla configuration."""

    def test_default_values(self):
        """Test default configuration values."""
        config = ValhallaConfig()
        assert config.base_url == ""
        assert config.timeout == 30.0
        assert config.api_key == ""


class TestConfig:
    """Tests for main configuration."""

    def test_default_values(self):
        """Test default configuration values."""
        config = Config()
        assert config.default_crs == "EPSG:4326"
        assert config.max_file_size_mb == 100
        assert config.temp_dir == "/tmp/locusync"
        assert isinstance(config.nominatim, NominatimConfig)
        assert isinstance(config.osrm, OSRMConfig)
        assert isinstance(config.valhalla, ValhallaConfig)

    def test_from_env_nominatim_url(self):
        """Test loading Nominatim URL from environment."""
        with patch.dict(os.environ, {"NOMINATIM_URL": "https://custom.nominatim.org"}):
            config = Config.from_env()
            assert config.nominatim.base_url == "https://custom.nominatim.org"

    def test_from_env_nominatim_user_agent(self):
        """Test loading Nominatim user agent from environment."""
        with patch.dict(os.environ, {"NOMINATIM_USER_AGENT": "custom-agent/1.0"}):
            config = Config.from_env()
            assert config.nominatim.user_agent == "custom-agent/1.0"

    def test_from_env_osrm_url(self):
        """Test loading OSRM URL from environment."""
        with patch.dict(os.environ, {"OSRM_URL": "https://custom.osrm.org"}):
            config = Config.from_env()
            assert config.osrm.base_url == "https://custom.osrm.org"

    def test_from_env_osrm_profile(self):
        """Test loading OSRM profile from environment."""
        with patch.dict(os.environ, {"OSRM_PROFILE": "cycling"}):
            config = Config.from_env()
            assert config.osrm.profile == "cycling"

    def test_from_env_valhalla_url(self):
        """Test loading Valhalla URL from environment."""
        with patch.dict(os.environ, {"VALHALLA_URL": "https://valhalla.example.org"}):
            config = Config.from_env()
            assert config.valhalla.base_url == "https://valhalla.example.org"

    def test_from_env_valhalla_api_key(self):
        """Test loading Valhalla API key from environment."""
        with patch.dict(os.environ, {"VALHALLA_API_KEY": "secret-key-123"}):
            config = Config.from_env()
            assert config.valhalla.api_key == "secret-key-123"

    def test_from_env_default_crs(self):
        """Test loading default CRS from environment."""
        with patch.dict(os.environ, {"GIS_DEFAULT_CRS": "EPSG:3857"}):
            config = Config.from_env()
            assert config.default_crs == "EPSG:3857"

    def test_from_env_temp_dir(self):
        """Test loading temp directory from environment."""
        with patch.dict(os.environ, {"GIS_TEMP_DIR": "/custom/temp"}):
            config = Config.from_env()
            assert config.temp_dir == "/custom/temp"

    def test_from_env_multiple_values(self):
        """Test loading multiple values from environment."""
        env_vars = {
            "NOMINATIM_URL": "https://nom.example.org",
            "OSRM_URL": "https://osrm.example.org",
            "GIS_DEFAULT_CRS": "EPSG:2154",
        }
        with patch.dict(os.environ, env_vars):
            config = Config.from_env()
            assert config.nominatim.base_url == "https://nom.example.org"
            assert config.osrm.base_url == "https://osrm.example.org"
            assert config.default_crs == "EPSG:2154"


class TestGetSetConfig:
    """Tests for global config functions."""

    def test_get_config_returns_instance(self):
        """Test that get_config returns a Config instance."""
        # Reset global config
        set_config(None)  # type: ignore

        config = get_config()
        assert isinstance(config, Config)

    def test_get_config_singleton(self):
        """Test that get_config returns the same instance."""
        set_config(None)  # type: ignore

        config1 = get_config()
        config2 = get_config()
        assert config1 is config2

    def test_set_config(self):
        """Test setting custom config."""
        custom_config = Config()
        custom_config.default_crs = "EPSG:3857"

        set_config(custom_config)
        retrieved = get_config()

        assert retrieved.default_crs == "EPSG:3857"
        assert retrieved is custom_config

        # Reset for other tests
        set_config(None)  # type: ignore
