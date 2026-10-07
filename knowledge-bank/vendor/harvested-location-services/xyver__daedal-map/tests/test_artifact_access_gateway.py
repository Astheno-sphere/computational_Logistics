import io
import os
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mapmover.api_query_commercial import trusted_artifact_tokens
from mapmover.artifact_access import artifact_token_records
from mapmover.routes import artifacts


class _ObjectStore:
    def __init__(self):
        self.calls = []

    def get_object(self, **kwargs):
        self.calls.append(("get", kwargs))
        return {
            "Body": io.BytesIO(b"artifact-bytes"),
            "ContentLength": 14,
            "ContentType": "application/octet-stream",
            "ETag": '"test-etag"',
        }

    def head_object(self, **kwargs):
        self.calls.append(("head", kwargs))
        return {
            "ContentLength": 14,
            "ContentType": "application/octet-stream",
            "ETag": '"test-etag"',
        }


class ArtifactAccessGatewayTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(artifacts.router)
        self.client = TestClient(app)
        self.store = _ObjectStore()
        self.env = patch.dict(
            os.environ,
            {
                "S3_BUCKET": "test-bucket",
                "ARTIFACT_ACCESS_TOKENS": "alice=alice-secret,bob-secret",
                "ARTIFACT_DOWNLOAD_RATE_LIMIT": "1000",
            },
            clear=False,
        )
        self.env.start()
        self.client_patch = patch.object(
            artifacts,
            "_s3_client",
            return_value=self.store,
        )
        self.client_patch.start()

    def tearDown(self):
        self.client_patch.stop()
        self.env.stop()

    def test_token_parser_supports_labels_and_plain_tokens(self):
        records = artifact_token_records()
        self.assertEqual(
            [(record.label, record.token) for record in records],
            [("alice", "alice-secret"), (None, "bob-secret")],
        )
        self.assertEqual(
            trusted_artifact_tokens(),
            {"alice-secret", "bob-secret"},
        )

    def test_downloadable_lane_is_anonymous(self):
        response = self.client.get("/api/artifacts/downloadable/packs/index.json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"artifact-bytes")
        self.assertEqual(
            self.store.calls[-1][1]["Key"],
            "downloadable/packs/index.json",
        )

    def test_published_and_staging_require_same_artifact_token(self):
        for lane in ("published", "staging"):
            unauthorized = self.client.get(f"/api/artifacts/{lane}/catalog.json")
            self.assertEqual(unauthorized.status_code, 401)
            self.assertEqual(
                unauthorized.headers.get("www-authenticate"),
                "Bearer",
            )

            authorized = self.client.get(
                f"/api/artifacts/{lane}/catalog.json",
                headers={"Authorization": "Bearer alice-secret"},
            )
            self.assertEqual(authorized.status_code, 200)
            self.assertEqual(
                self.store.calls[-1][1]["Key"],
                f"{lane}/catalog.json",
            )

    def test_control_lane_is_never_available(self):
        response = self.client.get(
            "/api/artifacts/control/pack_release_markers_latest.json",
            headers={"Authorization": "Bearer alice-secret"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json()["error"]["code"],
            "control_lane_forbidden",
        )

    def test_invalid_path_is_rejected_before_storage(self):
        before = len(self.store.calls)
        response = self.client.get(
            "/api/artifacts/published/../control/secret.json",
            headers={"Authorization": "Bearer alice-secret"},
        )
        self.assertIn(response.status_code, {400, 403, 404})
        self.assertEqual(len(self.store.calls), before)


if __name__ == "__main__":
    unittest.main()
