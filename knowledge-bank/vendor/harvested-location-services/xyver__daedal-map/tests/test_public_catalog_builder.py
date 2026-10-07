import json
import tempfile
import unittest
from pathlib import Path

from converters.catalog_builder import build_catalog


class PublicCatalogBuilderTests(unittest.TestCase):
    def test_preserves_pack_and_data_type_contract(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            data_root = Path(temp_dir)
            source_dir = data_root / "global" / "regional_health"
            source_dir.mkdir(parents=True)
            (source_dir / "metadata.json").write_text(
                json.dumps(
                    {
                        "source_id": "regional_health",
                        "source_name": "Regional Health",
                        "pack_id": "my_health_project",
                        "category": "health",
                        "data_type": "metrics",
                        "metrics": {},
                    }
                ),
                encoding="utf-8",
            )

            catalog = build_catalog(data_root)

            self.assertEqual(catalog["total_sources"], 1)
            source = catalog["sources"][0]
            self.assertEqual(source["pack_id"], "my_health_project")
            self.assertEqual(source["data_type"], "metrics")


if __name__ == "__main__":
    unittest.main()
