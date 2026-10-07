from __future__ import annotations

import json
import unittest
from pathlib import Path


CATALOG_PATH = (
    Path(__file__).resolve().parents[2]
    / "county-map-data"
    / "geometry"
    / "geometry_catalog.json"
)


class GeometryCatalogTaxonomyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))

    def test_schema_uses_canonical_object_names(self) -> None:
        self.assertEqual(self.catalog["schema_version"], "1.3.0")
        for key in (
            "geometry_collections",
            "geometry_families",
            "geometry_banks",
            "geometry_products",
            "release_packages",
            "crosswalk_artifacts",
            "resolver_groups",
            "named_reference_objects",
        ):
            self.assertIsInstance(self.catalog.get(key), list, key)
        self.assertNotIn("geometry_assets", self.catalog)
        self.assertNotIn("geometry_packages", self.catalog)
        self.assertNotIn("named_geometries", self.catalog)

    def test_marine_objects_share_collection_not_family(self) -> None:
        collections = {
            item["collection_id"]: item for item in self.catalog["geometry_collections"]
        }
        marine = collections["marine_reference"]
        objects = [
            item
            for item in self.catalog["named_reference_objects"]
            if item.get("collection_id") == "marine_reference"
        ]
        self.assertEqual(len(objects), marine["named_reference_object_count"])
        self.assertEqual({item["family"] for item in objects}, {"marine_eez", "water_body"})
        self.assertEqual(len({item["loc_id"] for item in objects}), len(objects))

    def test_catalog_lists_are_unique_and_sorted(self) -> None:
        checks = (
            ("geometry_families", lambda item: str(item.get("family") or "")),
            ("geometry_banks", lambda item: (str(item.get("family") or ""), str(item.get("bank_id") or ""))),
            ("geometry_products", lambda item: (str(item.get("product_group") or ""), str(item.get("family") or ""), str(item.get("product_id") or ""))),
            ("named_reference_objects", lambda item: (str(item.get("family") or ""), str(item.get("label") or ""), str(item.get("loc_id") or ""))),
        )
        id_fields = {
            "geometry_families": "family",
            "geometry_banks": "bank_id",
            "geometry_products": "product_id",
            "named_reference_objects": "loc_id",
        }
        for key, sort_key in checks:
            rows = self.catalog[key]
            self.assertEqual(rows, sorted(rows, key=sort_key), key)
            ids = [str(item.get(id_fields[key]) or "") for item in rows]
            self.assertTrue(all(ids), key)
            self.assertEqual(len(ids), len(set(ids)), key)

    def test_products_are_capabilities_not_release_packages(self) -> None:
        self.assertTrue(self.catalog["geometry_products"])
        self.assertTrue(self.catalog["release_packages"])
        family_ids = {item["family"] for item in self.catalog["geometry_families"]}
        product_ids = {item["product_id"] for item in self.catalog["geometry_products"]}
        for product in self.catalog["geometry_products"]:
            self.assertIn(product["product_kind"], {"shape_bank", "crosswalk"})
            self.assertIsInstance(product["family_ids"], list)
            self.assertTrue(set(product["family_ids"]).issubset(family_ids))
            self.assertNotIn("asset_id", product)
            # A product remains a stable capability even when it points to its
            # current published download. Versioned packages still live in the
            # separate release_packages collection below.
            download = product.get("download")
            if download is not None:
                self.assertTrue(download.get("available"))
                self.assertTrue(download.get("artifact_url"))
                self.assertNotIn("package_id", product)
        product_ids_from_releases = {
            str(item.get("geometry_product_id") or "")
            for item in self.catalog["release_packages"]
        }
        self.assertTrue(product_ids_from_releases.issubset(product_ids))
        self.assertTrue(all(item.get("package_id") for item in self.catalog["release_packages"]))
        for collection in self.catalog["geometry_collections"]:
            self.assertTrue(set(collection["family_ids"]).issubset(family_ids))
            self.assertTrue(set(collection["product_ids"]).issubset(product_ids))


if __name__ == "__main__":
    unittest.main()
