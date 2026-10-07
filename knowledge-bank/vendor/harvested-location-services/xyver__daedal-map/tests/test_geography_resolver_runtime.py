import unittest

from mapmover.runtime.geography_resolver import resolve_geography


class GeographyResolverRuntimeTests(unittest.TestCase):
    def test_bare_country_names_outrank_same_name_seas(self):
        cases = {
            "Iceland": "ISL",
            "Japan": "JPN",
            "Greenland": "GRL",
        }
        for query, expected in cases.items():
            with self.subTest(query=query):
                resolved = resolve_geography(query=query)
                self.assertEqual(resolved.get("outcome"), "ok")
                self.assertEqual(resolved.get("loc_ids"), [expected])
                self.assertEqual(resolved.get("locations", [{}])[0].get("family"), "admin_0")

    def test_explicit_named_seas_still_resolve_to_water_geometry(self):
        for query in ["Sea of Japan", "Japan Sea", "Mediterranean Sea"]:
            with self.subTest(query=query):
                resolved = resolve_geography(query=query)
                self.assertEqual(resolved.get("outcome"), "ok")
                self.assertEqual(resolved.get("locations", [{}])[0].get("family"), "water_body")

    def test_named_water_parent_expands_to_child_geometry_ids(self):
        resolved = resolve_geography(query="Mediterranean")
        self.assertEqual(resolved.get("outcome"), "ok")
        loc_ids = resolved.get("loc_ids") or []
        self.assertIn("IHO1953-240001002", loc_ids)
        self.assertIn("IHO1953-240001003", loc_ids)
        self.assertIn("IHO1953-240001004", loc_ids)
        self.assertIn("IHO1953-240001005", loc_ids)
        self.assertEqual(
            (resolved.get("provenance") or {}).get("expanded_from_loc_id"),
            "IHO1953-240001002",
        )


if __name__ == "__main__":
    unittest.main()
