from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from app import app
from mapmover import data_loading
from mapmover.private_mcp_loader import DEFAULT_PRIVATE_MCP_BUNDLE_ROOTS
from mapmover.runtime_env_files import runtime_env_file_candidates


class RepoSplitRuntimeBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original_extra_env_files = os.environ.get("COUNTY_MAP_EXTRA_ENV_FILES")
        self._original_agent_catalog_root = os.environ.get("COUNTY_MAP_AGENT_CATALOG_OUTPUT_ROOT")
        self._original_private_mcp_proxy_base_url = os.environ.get("PRIVATE_MCP_PROXY_BASE_URL")
        self._original_cloud_internal_api_token = os.environ.get("CLOUD_INTERNAL_API_TOKEN")

    def tearDown(self) -> None:
        if self._original_extra_env_files is None:
            os.environ.pop("COUNTY_MAP_EXTRA_ENV_FILES", None)
        else:
            os.environ["COUNTY_MAP_EXTRA_ENV_FILES"] = self._original_extra_env_files

        if self._original_agent_catalog_root is None:
            os.environ.pop("COUNTY_MAP_AGENT_CATALOG_OUTPUT_ROOT", None)
        else:
            os.environ["COUNTY_MAP_AGENT_CATALOG_OUTPUT_ROOT"] = self._original_agent_catalog_root

        if self._original_private_mcp_proxy_base_url is None:
            os.environ.pop("PRIVATE_MCP_PROXY_BASE_URL", None)
        else:
            os.environ["PRIVATE_MCP_PROXY_BASE_URL"] = self._original_private_mcp_proxy_base_url

        if self._original_cloud_internal_api_token is None:
            os.environ.pop("CLOUD_INTERNAL_API_TOKEN", None)
        else:
            os.environ["CLOUD_INTERNAL_API_TOKEN"] = self._original_cloud_internal_api_token

    def test_runtime_env_candidates_do_not_include_private_repo_by_default(self) -> None:
        os.environ.pop("COUNTY_MAP_EXTRA_ENV_FILES", None)
        workspace_root = Path(r"C:\workspace\global map")

        candidates = runtime_env_file_candidates(workspace_root)
        candidate_texts = [str(path) for path in candidates]

        self.assertIn(str(workspace_root / "county-map" / ".env"), candidate_texts)
        self.assertIn(str(workspace_root / ".env"), candidate_texts)
        self.assertNotIn(str(workspace_root / "county-map-private" / ".env"), candidate_texts)

    def test_runtime_env_candidates_allow_explicit_extra_files(self) -> None:
        workspace_root = Path(r"C:\workspace\global map")
        private_env = workspace_root / "county-map-private" / ".env"
        os.environ["COUNTY_MAP_EXTRA_ENV_FILES"] = str(private_env)

        candidates = runtime_env_file_candidates(workspace_root)

        self.assertIn(private_env, candidates)

    def test_private_mcp_loader_defaults_allow_hosted_private_bundle_roots_only(self) -> None:
        root_texts = {str(path) for path in DEFAULT_PRIVATE_MCP_BUNDLE_ROOTS}

        self.assertIn(str(Path("/app/private_mcp_tools")), root_texts)
        self.assertIn(str(Path("/app/county-map-private/tools")), root_texts)
        self.assertFalse(any(r"C:\workspace\global map\county-map-private" in text for text in root_texts))

    def test_agent_catalog_output_root_uses_env_override(self) -> None:
        override = r"C:\tmp\agent-catalog-output"
        os.environ["COUNTY_MAP_AGENT_CATALOG_OUTPUT_ROOT"] = override

        self.assertEqual(data_loading._agent_catalog_output_root(), Path(override))

    def test_api_pack_detail_hydration_strips_private_browser_artifact_paths(self) -> None:
        payload = {
            "pack_id": "demo_pack",
            "sources": [
                {
                    "source_id": "demo_source",
                    "browser_artifact": {"storage_key": "stale/value.json.gz"},
                }
            ],
        }
        metadata = {
            "browser_artifact": {
                "storage_key": "published/browser_artifacts/sources/demo_source/runtime_snapshot_v1.json.gz",
                "sha256": "abc123",
                "transfer_bytes": 10,
                "stored_bytes": 10,
                "expanded_bytes": 20,
                "generated_at": "2026-06-30T00:00:00Z",
                "local_artifact_path": "/opt/global-map/repo/county-map-private/build/browser_artifacts/output/published/browser_artifacts/sources/demo_source/runtime_snapshot_v1.json.gz",
            }
        }

        with mock.patch("mapmover.data_loading.load_source_metadata", return_value=metadata):
            hydrated = data_loading._hydrate_api_pack_detail_from_source_metadata(payload)

        source = hydrated["sources"][0]
        artifact = source["browser_artifact"]
        self.assertEqual(
            artifact["storage_key"],
            "published/browser_artifacts/sources/demo_source/runtime_snapshot_v1.json.gz",
        )
        self.assertNotIn("local_artifact_path", artifact)

    def test_private_mcp_route_proxies_to_private_runtime_when_local_bundle_missing(self) -> None:
        class FakeResponse:
            def __init__(self) -> None:
                self.content = b'{"private": true, "transport": "streamable-http"}'
                self.status_code = 200
                self.headers = {
                    "Content-Type": "application/json",
                    "MCP-Protocol-Version": "2025-06-18",
                    "Cache-Control": "no-store",
                }

        captured: dict[str, object] = {}

        def fake_request(method: str, url: str, data=None, headers=None, timeout=None):
            captured["method"] = method
            captured["url"] = url
            captured["data"] = data
            captured["headers"] = headers
            captured["timeout"] = timeout
            return FakeResponse()

        os.environ["PRIVATE_MCP_PROXY_BASE_URL"] = "https://private.example"
        os.environ["CLOUD_INTERNAL_API_TOKEN"] = "internal_test_token"
        client = TestClient(app)

        with mock.patch("mapmover.routes.private_mcp.get_private_mcp_provider", return_value=None):
            with mock.patch("mapmover.routes.private_mcp.requests.request", side_effect=fake_request):
                response = client.post(
                    "/mcp-private/grants",
                    headers={"Authorization": "Bearer granttest1"},
                    json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["private"], True)
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["url"], "https://private.example/internal/mcp/grants")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer granttest1")
        self.assertEqual(captured["headers"]["x-internal-api-key"], "internal_test_token")
        self.assertIn(b'"method":"tools/list"', captured["data"])


if __name__ == "__main__":
    unittest.main()
