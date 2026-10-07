from __future__ import annotations

import io
import os
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from mapmover import duckdb_helpers
from mapmover.runtime import published_artifacts


class PublishedArtifactTests(unittest.TestCase):
    def test_default_file_limit_accommodates_large_reference_graph(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(1024 * 1024 * 1024, published_artifacts.artifact_cache_max_file_bytes())

    def _config(self) -> dict:
        return {
            "cloud": {
                "bucket": "config-bucket",
                "prefix": "config-prefix",
                "endpoint_url": "https://config.example",
            }
        }

    def test_published_ref_owns_prefix_and_storage_configuration(self) -> None:
        env = {
            "S3_BUCKET": "runtime-bucket",
            "S3_PREFIX": "active-candidate",
            "S3_PUBLISHED_PREFIX": "published-v7",
            "S3_ENDPOINT_URL": "https://objects.example",
            "AWS_DEFAULT_REGION": "auto",
        }
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(
            published_artifacts, "get_runtime_config", return_value=self._config()
        ):
            ref = published_artifacts.artifact_ref("geometry/catalog.json")

        self.assertEqual(ref.bucket, "runtime-bucket")
        self.assertEqual(ref.key, "published-v7/geometry/catalog.json")
        self.assertEqual(ref.uri, "s3://runtime-bucket/published-v7/geometry/catalog.json")
        self.assertEqual(ref.endpoint_url, "https://objects.example")

    def test_active_lane_preserves_active_prefix(self) -> None:
        with mock.patch.dict(os.environ, {
            "S3_BUCKET": "bucket", "S3_PREFIX": "candidate", "S3_PUBLISHED_PREFIX": "published"
        }, clear=True), mock.patch.object(
            published_artifacts, "get_runtime_config", return_value=self._config()
        ):
            ref = published_artifacts.artifact_ref("catalog.json", lane="active")

        self.assertEqual(ref.key, "candidate/catalog.json")

    def test_unsafe_relative_paths_are_rejected(self) -> None:
        with mock.patch.dict(os.environ, {"S3_BUCKET": "bucket"}, clear=True), mock.patch.object(
            published_artifacts, "get_runtime_config", return_value=self._config()
        ):
            for value in ("", ".", "../secret.json", "geometry/../../secret.json", "/secret.json", "C:/secret.json"):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    published_artifacts.artifact_ref(value)

    def test_data_artifact_ref_requires_path_below_data_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.dict(
            os.environ, {"S3_BUCKET": "bucket"}, clear=True
        ), mock.patch.object(published_artifacts, "get_runtime_config", return_value=self._config()):
            root = Path(temp_dir) / "data"
            inside = root / "geometry" / "countries" / "CAN" / "geometry.parquet"
            ref = published_artifacts.data_artifact_ref(inside, data_root=root)
            self.assertEqual(ref.relative_path, "geometry/countries/CAN/geometry.parquet")
            with self.assertRaises(ValueError):
                published_artifacts.data_artifact_ref(Path(temp_dir) / "outside.parquet", data_root=root)

    def test_json_read_uses_canonical_ref(self) -> None:
        response = {"Body": io.BytesIO(b'{"status":"ok"}')}
        client = mock.Mock()
        client.head_object.side_effect = OSError("cache metadata unavailable")
        client.get_object.return_value = response
        with mock.patch.dict(os.environ, {
            "S3_BUCKET": "bucket", "S3_PUBLISHED_PREFIX": "published"
        }, clear=True), mock.patch.object(
            published_artifacts, "get_runtime_config", return_value=self._config()
        ), mock.patch.object(published_artifacts, "_object_store_client", return_value=client):
            payload = published_artifacts.read_artifact_json("graph/metadata.json")

        self.assertEqual(payload, {"status": "ok"})
        client.get_object.assert_called_once_with(
            Bucket="bucket", Key="published/graph/metadata.json"
        )

    def test_duckdb_path_translation_uses_shared_artifact_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.dict(os.environ, {
            "S3_BUCKET": "bucket", "S3_PREFIX": "active",
            "PUBLISHED_ARTIFACT_CACHE_ENABLED": "false",
        }, clear=True), mock.patch.object(
            published_artifacts, "get_runtime_config", return_value=self._config()
        ), mock.patch.object(duckdb_helpers, "is_cloud_mode", return_value=True), mock.patch.object(
            duckdb_helpers, "_allow_local_source_fallback", return_value=False
        ), mock.patch.object(duckdb_helpers, "_get_data_root", return_value=Path(temp_dir)):
            uri = duckdb_helpers.path_to_uri(Path(temp_dir) / "global" / "pack" / "data.parquet")

        self.assertEqual(uri, "s3://bucket/active/global/pack/data.parquet")

    def test_hydrates_once_then_serves_verified_disk_hit(self) -> None:
        payload = b"verified artifact"
        client = mock.Mock()
        client.head_object.return_value = {
            "ContentLength": len(payload), "ETag": '"etag-1"',
            "LastModified": datetime(2026, 8, 12, tzinfo=timezone.utc),
        }
        client.get_object.side_effect = lambda **_kwargs: {"Body": io.BytesIO(payload)}
        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.dict(os.environ, {
            "S3_BUCKET": "bucket", "S3_PUBLISHED_PREFIX": "published",
            "PUBLISHED_ARTIFACT_CACHE_DIR": temp_dir,
            "PUBLISHED_ARTIFACT_CACHE_ENABLED": "true",
        }, clear=True), mock.patch.object(
            published_artifacts, "get_runtime_config", return_value=self._config()
        ), mock.patch.object(published_artifacts, "_object_store_client", return_value=client):
            first = published_artifacts.resolve_artifact_path("geometry/test.parquet")
            second = published_artifacts.resolve_artifact_path("geometry/test.parquet")

            self.assertIsNotNone(first)
            self.assertEqual(first, second)
            self.assertEqual(first.read_bytes(), payload)

        self.assertEqual(client.get_object.call_count, 1)
        self.assertEqual(client.head_object.call_count, 1)

    def test_corrupt_cached_file_is_rehydrated(self) -> None:
        payload = b"correct bytes"
        client = mock.Mock()
        client.head_object.return_value = {"ContentLength": len(payload), "ETag": '"same"'}
        client.get_object.side_effect = lambda **_kwargs: {"Body": io.BytesIO(payload)}
        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.dict(os.environ, {
            "S3_BUCKET": "bucket", "PUBLISHED_ARTIFACT_CACHE_DIR": temp_dir,
            "PUBLISHED_ARTIFACT_CACHE_ENABLED": "true",
        }, clear=True), mock.patch.object(
            published_artifacts, "get_runtime_config", return_value=self._config()
        ), mock.patch.object(published_artifacts, "_object_store_client", return_value=client):
            path = published_artifacts.resolve_artifact_path("catalog.json")
            self.assertIsNotNone(path)
            path.write_bytes(b"corrupt")
            restored = published_artifacts.resolve_artifact_path("catalog.json")
            self.assertEqual(restored.read_bytes(), payload)

        self.assertEqual(client.get_object.call_count, 2)

    def test_large_artifact_keeps_remote_duckdb_uri(self) -> None:
        client = mock.Mock()
        client.head_object.return_value = {"ContentLength": 3 * 1024 * 1024, "ETag": '"large"'}
        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.dict(os.environ, {
            "S3_BUCKET": "bucket", "S3_PREFIX": "published",
            "PUBLISHED_ARTIFACT_CACHE_DIR": str(Path(temp_dir) / "cache"),
            "PUBLISHED_ARTIFACT_CACHE_ENABLED": "true",
            "PUBLISHED_ARTIFACT_CACHE_MAX_FILE_MB": "1",
            "PUBLISHED_ARTIFACT_CACHE_QUERY_MAX_FILE_MB": "1",
        }, clear=True), mock.patch.object(
            published_artifacts, "get_runtime_config", return_value=self._config()
        ), mock.patch.object(published_artifacts, "_object_store_client", return_value=client), mock.patch.object(
            duckdb_helpers, "is_cloud_mode", return_value=True
        ), mock.patch.object(duckdb_helpers, "_allow_local_source_fallback", return_value=False), mock.patch.object(
            duckdb_helpers, "_get_data_root", return_value=Path(temp_dir)
        ):
            uri = duckdb_helpers.path_to_uri(Path(temp_dir) / "large.parquet")

        self.assertEqual(uri, "s3://bucket/published/large.parquet")
        client.get_object.assert_not_called()

    def test_query_path_keeps_large_parquet_remote_even_with_larger_hydration_limit(self) -> None:
        client = mock.Mock()
        client.head_object.return_value = {"ContentLength": 64 * 1024 * 1024, "ETag": '"large"'}
        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.dict(os.environ, {
            "S3_BUCKET": "bucket", "S3_PREFIX": "published",
            "PUBLISHED_ARTIFACT_CACHE_ENABLED": "true",
            "PUBLISHED_ARTIFACT_CACHE_MAX_FILE_MB": "1024",
            "PUBLISHED_ARTIFACT_CACHE_QUERY_MAX_FILE_MB": "32",
        }, clear=True), mock.patch.object(
            published_artifacts, "get_runtime_config", return_value=self._config()
        ), mock.patch.object(published_artifacts, "_object_store_client", return_value=client), mock.patch.object(
            duckdb_helpers, "is_cloud_mode", return_value=True
        ), mock.patch.object(duckdb_helpers, "_allow_local_source_fallback", return_value=False), mock.patch.object(
            duckdb_helpers, "_get_data_root", return_value=Path(temp_dir)
        ):
            uri = duckdb_helpers.path_to_uri(Path(temp_dir) / "geometry" / "countries" / "USA" / "admin_spine.parquet")

        self.assertEqual(uri, "s3://bucket/published/geometry/countries/USA/admin_spine.parquet")
        client.get_object.assert_not_called()

    def test_recent_cache_path_is_not_unlinked_during_eviction(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.dict(os.environ, {
            "PUBLISHED_ARTIFACT_CACHE_DIR": temp_dir,
            "PUBLISHED_ARTIFACT_CACHE_QUOTA_MB": "1",
            "PUBLISHED_ARTIFACT_CACHE_EVICTION_GRACE_SECONDS": "120",
        }, clear=True):
            objects = Path(temp_dir) / "objects" / "aa"
            objects.mkdir(parents=True)
            recent = objects / "recent.parquet"
            recent.write_bytes(b"x" * 800_000)
            entries = {
                "recent": {
                    "local_path": str(recent),
                    "bytes": recent.stat().st_size,
                    "last_accessed": time.time(),
                }
            }

            admitted = published_artifacts._evict_for(
                entries, 800_000, keep_key="incoming"
            )

            self.assertFalse(admitted)
            self.assertTrue(recent.is_file())
            self.assertIn("recent", entries)


if __name__ == "__main__":
    unittest.main()
