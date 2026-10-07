"""
Storage Manager for Recommendation Module
"""

import asyncio
import json
from pathlib import Path
from typing import Any


class RecommendationStorageManager:
    """
    Storage Manager for Recommendation Module
    """

    def __init__(self, data_dir: Path):
        """
        Initialize the Recommendation Storage Manager

        :param data_dir: Base data directory (e.g., Path("data/social_media"))
        """
        self.data_dir = Path(data_dir) / "recommendation"
        self._lock = asyncio.Lock()

        # Create directories
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.models_dir = self.data_dir / "models"
        self.configs_dir = self.data_dir / "configs"
        self.models_dir.mkdir(exist_ok=True)
        self.configs_dir.mkdir(exist_ok=True)

        # File paths
        self.items_file = self.data_dir / "items.json"
        self.ratings_file = self.data_dir / "ratings.json"
        self.preferences_file = self.data_dir / "user_preferences.json"
        self.cache_file = self.data_dir / "feed_cache.json"
        self.history_file = self.data_dir / "recommendation_history.json"

    async def _read_json(self, file_path: Path) -> dict[str, Any]:
        """Read JSON file"""
        async with self._lock:
            if not file_path.exists():
                return {}

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data
            except json.JSONDecodeError:
                return {}
            except Exception as e:
                raise OSError(f"Failed to read {file_path}: {e}") from e

    async def _write_json(self, file_path: Path, data: dict[str, Any]) -> None:
        """Write JSON file (atomic write)"""
        async with self._lock:
            try:
                temp_file = file_path.with_suffix(".tmp")
                with open(temp_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                temp_file.replace(file_path)
            except Exception as e:
                raise OSError(f"Failed to write {file_path}: {e}") from e

    async def _read_json_list(self, file_path: Path) -> list[dict[str, Any]]:
        """Read JSON file as a list"""
        async with self._lock:
            if not file_path.exists():
                return []

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data if isinstance(data, list) else []
            except json.JSONDecodeError:
                return []
            except Exception as e:
                raise OSError(f"Failed to read {file_path}: {e}") from e

    async def _write_json_list(
        self, file_path: Path, data: list[dict[str, Any]]
    ) -> None:
        """Write JSON file as a list (atomic write)"""
        async with self._lock:
            try:
                temp_file = file_path.with_suffix(".tmp")
                with open(temp_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                temp_file.replace(file_path)
            except Exception as e:
                raise OSError(f"Failed to write {file_path}: {e}") from e

    # ===== Items =====

    async def load_items(self) -> dict[int, dict[str, Any]]:
        """Load all items"""
        data = await self._read_json(self.items_file)
        return {int(k): v for k, v in data.items()}

    async def save_items(self, items: dict[int, dict[str, Any]]) -> None:
        """Save all items"""
        data = {str(k): v for k, v in items.items()}
        await self._write_json(self.items_file, data)

    # ===== Ratings =====

    async def load_ratings(self) -> list[dict[str, Any]]:
        """Load all ratings"""
        return await self._read_json_list(self.ratings_file)

    async def save_ratings(self, ratings: list[dict[str, Any]]) -> None:
        """Save all ratings"""
        await self._write_json_list(self.ratings_file, ratings)

    # ===== User Preferences =====

    async def load_user_preferences(self) -> dict[int, dict[str, Any]]:
        """Load user preferences"""
        data = await self._read_json(self.preferences_file)
        return {int(k): v for k, v in data.items()}

    async def save_user_preferences(
        self, preferences: dict[int, dict[str, Any]]
    ) -> None:
        """Save user preferences"""
        data = {str(k): v for k, v in preferences.items()}
        await self._write_json(self.preferences_file, data)

    # ===== Feed Cache =====

    async def load_feed_cache(self) -> dict[str, dict[str, Any]]:
        """Load feed cache (key: f"{user_id}_{algorithm}")"""
        return await self._read_json(self.cache_file)

    async def save_feed_cache(self, cache: dict[str, dict[str, Any]]) -> None:
        """Save feed cache"""
        await self._write_json(self.cache_file, cache)

    # ===== Recommendation History =====

    async def load_recommendation_history(self) -> list[dict[str, Any]]:
        """Load recommendation history"""
        return await self._read_json_list(self.history_file)

    async def save_recommendation_history(self, history: list[dict[str, Any]]) -> None:
        """Save recommendation history"""
        await self._write_json_list(self.history_file, history)

    # ===== Models =====

    def get_model_path(self, algorithm: str) -> Path:
        """Get model file path for an algorithm"""
        return self.models_dir / f"{algorithm}_model.pth"

    def get_config_path(self, algorithm: str) -> Path:
        """Get config file path for an algorithm"""
        return self.configs_dir / f"{algorithm}_config.json"

    async def save_model_config(self, algorithm: str, config: dict[str, Any]) -> None:
        """Save algorithm configuration"""
        config_path = self.get_config_path(algorithm)
        await self._write_json(config_path, config)

    async def load_model_config(self, algorithm: str) -> dict[str, Any] | None:
        """Load algorithm configuration"""
        config_path = self.get_config_path(algorithm)
        if config_path.exists():
            return await self._read_json(config_path)
        return None


__all__ = ["RecommendationStorageManager"]
