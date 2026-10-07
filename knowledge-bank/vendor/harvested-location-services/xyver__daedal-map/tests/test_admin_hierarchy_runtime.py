import unittest
from unittest.mock import patch

import pandas as pd

from mapmover.runtime.admin_hierarchy import (
    get_ancestors,
    get_children,
    get_parent_loc_id,
    infer_admin_level_from_loc_id,
)


class AdminHierarchyRuntimeTests(unittest.TestCase):
    def test_infer_admin_level_handles_admin_spine_and_nuts_shapes(self):
        self.assertEqual(infer_admin_level_from_loc_id("USA"), 0)
        self.assertEqual(infer_admin_level_from_loc_id("USA-VA"), 1)
        self.assertEqual(infer_admin_level_from_loc_id("USA-VA-059"), 2)
        self.assertEqual(infer_admin_level_from_loc_id("USA-VA-059-452400"), 3)
        self.assertEqual(infer_admin_level_from_loc_id("FRA"), 0)
        self.assertEqual(infer_admin_level_from_loc_id("FRA-FR1"), 1)
        self.assertEqual(infer_admin_level_from_loc_id("FRA-FR10"), 2)
        self.assertEqual(infer_admin_level_from_loc_id("FRA-FR101"), 3)

    def test_parent_loc_id_uses_string_parent_chain_for_admin_spine(self):
        self.assertEqual(get_parent_loc_id("USA-VA-059"), "USA-VA")
        self.assertEqual(get_parent_loc_id("USA-VA-059-452400-1"), "USA-VA-059-452400")
        self.assertEqual(get_parent_loc_id("CAN-BC-5931-021-0221-067"), "CAN-BC-5931-021-0221")
        self.assertEqual(get_parent_loc_id("USA"), None)

    def test_parent_loc_id_handles_nuts_parent_chain(self):
        self.assertEqual(get_parent_loc_id("FRA-FR101"), "FRA-FR10")
        self.assertEqual(get_parent_loc_id("FRA-FR10"), "FRA-FR1")
        self.assertEqual(get_parent_loc_id("FRA-FR1"), "FRA")

    def test_get_ancestors_returns_full_chain(self):
        self.assertEqual(
            get_ancestors("USA-VA-059-452400-1"),
            ["USA-VA-059-452400", "USA-VA-059", "USA-VA", "USA"],
        )

    def test_canada_compact_source_components_preserve_depth_and_ancestors(self):
        loc_id = "CAN-BC-5931-021-0221-067"
        self.assertEqual(infer_admin_level_from_loc_id(loc_id), 5)
        self.assertEqual(
            get_ancestors(loc_id),
            [
                "CAN-BC-5931-021-0221",
                "CAN-BC-5931-021",
                "CAN-BC-5931",
                "CAN-BC",
                "CAN",
            ],
        )

    def test_get_children_loads_admin_base_and_translates_back_to_local(self):
        base_df = pd.DataFrame(
            [
                {"loc_id": "USA-G125186-G215213", "parent_id": "USA-G125186", "admin_level": 2},
                {"loc_id": "USA-G125186-G999999", "parent_id": "USA-G125186", "admin_level": 2},
            ]
        )
        translation_map = {
            "USA-VA": "USA-G125186",
            "USA-G125186-G215213": "USA-VA-059",
            "USA-G125186-G999999": "USA-VA-001",
        }

        with patch("mapmover.runtime.admin_hierarchy._load_base_geometry_frame", return_value=base_df), patch(
            "mapmover.runtime.admin_hierarchy.translate_loc_id_to_geometry_id",
            side_effect=lambda value: translation_map.get(value, value),
        ), patch(
            "mapmover.runtime.admin_hierarchy.translate_geometry_id_to_local_id",
            side_effect=lambda value: translation_map.get(value, value),
        ):
            children = get_children("USA-VA")

        self.assertEqual(children, ["USA-VA-059", "USA-VA-001"])

    def test_get_children_loads_subcounty_frame_for_deep_admin(self):
        subcounty_df = pd.DataFrame(
            [
                {"loc_id": "USA-VA-059-452400", "parent_id": "USA-VA-059"},
                {"loc_id": "USA-VA-059-453000", "parent_id": "USA-VA-059"},
            ]
        )

        with patch("mapmover.runtime.admin_hierarchy.load_subcounty_geometry", return_value=subcounty_df):
            children = get_children("USA-VA-059")

        self.assertEqual(children, ["USA-VA-059-452400", "USA-VA-059-453000"])


if __name__ == "__main__":
    unittest.main()
