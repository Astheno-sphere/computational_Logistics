import unittest

from mapmover.runtime.filter_primitives import normalize_sort_spec
from mapmover.runtime.postprocess_normalization import normalize_item_filters


class PostprocessNormalizationRuntimeTests(unittest.TestCase):
    def test_normalize_item_filters_maps_dimension_name_alias_to_column(self):
        item = {
            "source_id": "fairfax_buildings",
            "filters": {
                "building_type": "C",
            },
        }

        metadata = {
            "filterable_fields": ["loc_id", "TYPE", "BLDG_HEIGHT"],
            "dimensions": {
                "TYPE": {
                    "column": "TYPE",
                    "name": "Building Type",
                }
            },
        }

        normalize_item_filters(
            item,
            {"filterable_fields": ["loc_id", "TYPE", "BLDG_HEIGHT"]},
            load_source_metadata_func=lambda _source_id: metadata,
        )

        self.assertEqual(item["filters"], {"TYPE": "C"})

    def test_normalize_sort_spec_supports_order_only_tokens(self):
        self.assertEqual(normalize_sort_spec("descending"), {"order": "desc"})
        self.assertEqual(normalize_sort_spec("ascending"), {"order": "asc"})


if __name__ == "__main__":
    unittest.main()
