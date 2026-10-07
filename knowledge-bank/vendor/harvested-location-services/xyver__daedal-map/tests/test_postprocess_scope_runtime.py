import unittest

from mapmover.runtime.postprocess_normalization import normalize_source_declared_scope


class PostprocessScopeRuntimeTests(unittest.TestCase):
    def test_normalize_source_declared_scope_prefers_loc_id_anchor(self):
        item = {
            "source_id": "fairfax_buildings",
            "region": "usa-va-fairfax",
        }

        metadata = {
            "scope": {
                "canonical_region": "usa-va-fairfax",
                "loc_id_anchor": "USA-VA-059",
                "region_aliases": ["fairfax county", "fairfax"],
            }
        }

        normalized = normalize_source_declared_scope(
            item,
            load_source_metadata_func=lambda _source_id: {},
            load_source_reference_func=lambda _source_id: metadata,
        )

        self.assertEqual(normalized["region"], "USA-VA-059")


if __name__ == "__main__":
    unittest.main()
