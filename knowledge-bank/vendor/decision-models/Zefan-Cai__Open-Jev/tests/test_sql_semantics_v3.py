"""Hand-calculated business fixtures and separate SQLite result replay."""
import copy
from collections import defaultdict
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from jev import sql_semantics_v3 as sql


def fixture(family, events, extra=None, parameters=None):
    rows = [{"event_id": i + 1, "customer_id": i % 2 + 1,
             "activity_day": i + 1, **values} for i, values in enumerate(events)]
    tables = {"events": rows, **(extra or {})}
    schema = []
    for table, records in tables.items():
        columns = [f"{name} " + ("TEXT" if isinstance(value, str) else "INTEGER")
                   for name, value in records[0].items()]
        schema.append(f"CREATE TABLE {table} ({', '.join(columns)});")
    return {"schema": schema, "tables": tables, "parameters": parameters or {},
            "business_request": sql.REQUESTS[family][0]}


def independent_sqlite(state, queries):
    """Different loading path: execute explicit INSERTs, no generator database helper."""
    connection = sqlite3.connect(":memory:")
    try:
        connection.executescript("\n".join(state["schema"]))
        for table, records in state["tables"].items():
            for record in records:
                columns = list(record)
                connection.execute(f"INSERT INTO {table} ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
                                   list(record.values()))
        return [[list(result) for result in connection.execute(query)] for query in queries]
    finally:
        connection.close()


class SQLSemanticsV3Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = list(sql.generate(groups_per_family=1))

    def test_hand_calculated_fixtures_cover_every_business_operator(self):
        # Expected values are written independently, not obtained from generator SQL.
        examples = [
            ("extended_amount", [{"amount": 10, "quantity": 3}, {"amount": 7, "quantity": 2}], {}, {}, (44, 17)),
            ("distinct_customers", [{"amount": 1, "customer_id": 4}, {"amount": 2, "customer_id": 4},
                                    {"amount": 3, "customer_id": None}], {}, {}, (1, 3)),
            ("null_average", [{"amount": 6}, {"amount": None}, {"amount": 0}], {}, {}, (3, 2)),
            ("time_window", [{"amount": 2}, {"amount": 5}, {"amount": 7}, {"amount": 11}], {},
                            {"start_day": 2, "end_day": 4}, (12, 23)),
            ("unit_conversion", [{"amount": 3, "unit": "dollar"}, {"amount": 25, "unit": "cent"}], {}, {}, (325, 3.25)),
            ("refund_netting", [{"amount": 10}, {"amount": 20}],
             {"refunds": [{"refund_id": 1, "event_id": 1, "refund_amount": 2, "refund_status": "settled"},
                          {"refund_id": 2, "event_id": 1, "refund_amount": 3, "refund_status": "settled"},
                          {"refund_id": 3, "event_id": 2, "refund_amount": 9, "refund_status": "pending"}]}, {}, (25, 30)),
            ("join_multiplicity", [{"amount": 10}, {"amount": 10}, {"amount": 50}],
             {"tags": [{"tag_id": 1, "event_id": 1, "tag": "x"}, {"tag_id": 2, "event_id": 1, "tag": "x"},
                       {"tag_id": 3, "event_id": 2, "tag": "x"}]}, {"target_tag": "x"}, (20, 30)),
            ("anti_join_nulls", [{"amount": 1, "customer_id": 1}, {"amount": 2, "customer_id": None}],
             {"directory": [{"customer_id": 1}, {"customer_id": 2}, {"customer_id": 3}]}, {}, (2, 1)),
            ("weighted_rate", [{"amount": 0, "successes": 1, "trials": 2}, {"amount": 0, "successes": 2, "trials": 10}],
             {}, {}, (.25, .35)),
            ("group_threshold", [{"amount": 6, "customer_id": 1}, {"amount": 6, "customer_id": 1},
                                 {"amount": 15, "customer_id": 2}, {"amount": 20, "customer_id": 2}],
             {}, {"threshold": 10}, (2, 1)),
            ("latest_snapshot", [{"amount": 9, "customer_id": 1, "activity_day": 1},
                                 {"amount": 4, "customer_id": 1, "activity_day": 3},
                                 {"amount": 6, "customer_id": 1, "activity_day": 3},
                                 {"amount": 8, "customer_id": 2, "activity_day": 1},
                                 {"amount": 2, "customer_id": 2, "activity_day": 2}], {}, {}, (8, 17)),
            ("left_join_zeros", [{"amount": 4, "customer_id": 1}, {"amount": 8, "customer_id": 1},
                                {"amount": 6, "customer_id": 2}],
             {"directory": [{"customer_id": 1}, {"customer_id": 2}, {"customer_id": 3}]}, {}, (6, 9)),
        ]
        self.assertEqual({e[0] for e in examples}, set(sql.REQUESTS))
        for family, events, extra, parameters, answers in examples:
            with self.subTest(family=family):
                state = fixture(family, events, extra, parameters)
                for cte in (False, True):
                    options = sql.candidate_queries(family, state, {"normalized_customers": False, "cte": cte})
                    independently_executed = independent_sqlite(state, options)
                    self.assertEqual(independently_executed, sql.execute_candidates(state, options))
                    for mode, expected in enumerate(answers):
                        state["business_request"] = sql.REQUESTS[family][mode]
                        self.assertEqual(sql.business_result(state), [[expected]])
                        target, actual, values = sql.target_for(state, options)
                        self.assertEqual(actual, [[expected]])
                        for probability, result in zip(target, values):
                            self.assertEqual(probability > 0, result == [[expected]])

    def test_halfway_rounding_matches_stated_business_rule(self):
        state = fixture("weighted_rate", [{"amount": 0, "successes": 49, "trials": 128}])
        self.assertEqual(sql.business_result(state), [[.382813]])
        options = sql.candidate_queries("weighted_rate", state, {"normalized_customers": False, "cte": False})
        self.assertEqual(sql.execute_candidates(state, options)[0], [[.382813]])
        self.assertEqual(sql.round_business(-.3828125, 6), -.382813)

    def test_full_layout_smoke_independent_sqlite_replay(self):
        report = sql.audit_records(self.rows)
        self.assertEqual(report["summary"]["records"], 192)
        self.assertEqual(report["unique_databases"], 96)
        self.assertEqual(report["sql_structural_families"], 96)
        self.assertEqual(report["summary"]["splits"], {"train": 96, "calibration": 24, "validation": 24, "test": 24, "ood": 24})
        for row in self.rows:
            results = independent_sqlite(row["state"], row["options"])
            self.assertEqual(results, row["metadata"]["candidate_results"])
        self.assertTrue(all(report["checks"].values()))

    def test_equal_answers_are_not_mislabeled_as_negatives(self):
        row = next(row for row in self.rows if row["metadata"]["semantic_operator"] == "anti_join_nulls"
                   and row["metadata"]["provenance"]["variant"] == 0)
        self.assertEqual(sorted(row["target"]), [0, 0, .5, .5])
        reversed_target, _, _ = sql.target_for(row["state"], list(reversed(row["options"])))
        self.assertEqual(reversed_target, list(reversed(row["target"])))

    def test_syntax_errors_writes_and_multiple_statements_are_rejected(self):
        state = self.rows[0]["state"]
        bad = ["SELECT missing FROM events;", "DELETE FROM events;", "SELECT 1; DROP TABLE events;",
               "WITH x AS (SELECT 1) DELETE FROM events;", "SELECT 1 UNION ALL SELECT 2;"]
        for query in bad:
            with self.subTest(query=query), self.assertRaises(ValueError):
                sql.execute_candidates(state, [query])
        self.assertEqual(sql.execute_candidates(state, ["SELECT NULL;"]), [[[None]]])
        connection = sql.database(state)
        try:
            with self.assertRaises(sqlite3.Error):
                connection.execute("DROP TABLE events")
            self.assertGreater(connection.execute("SELECT COUNT(*) FROM events").fetchone()[0], 0)
        finally:
            connection.close()

    def test_label_result_and_visible_data_tampering_are_detected(self):
        for change in ("label", "result", "data"):
            rows = copy.deepcopy(self.rows)
            row = rows[0]
            if change == "label":
                row["target"] = [1 / len(row["options"])] * len(row["options"])
            elif change == "result":
                row["metadata"]["reference_result"] = [[-999]]
            else:
                row["state"]["tables"]["events"][0]["amount"] += 19
            with self.subTest(change=change), self.assertRaises(ValueError):
                sql.audit_records(rows)

    def test_counterfactuals_change_exactly_the_visible_requested_metric(self):
        groups = defaultdict(list)
        for row in self.rows:
            groups[row["group_id"]].append(row)
        for first, second in groups.values():
            self.assertEqual([key for key in first["state"] if first["state"][key] != second["state"][key]], ["business_request"])
            self.assertEqual(first["options"], second["options"])
            self.assertNotEqual(sql.business_result(first["state"]), sql.business_result(second["state"]))
            self.assertNotEqual(first["target"], second["target"])
            self.assertEqual(first["split"], second["split"])

    def test_metadata_never_determines_answer_and_no_results_in_inputs(self):
        row = copy.deepcopy(self.rows[0])
        expected = sql.target_for(row["state"], row["options"])[0]
        row["metadata"] = {"reference_result": [[-999]], "semantic_operator": "wrong"}
        row["target"] = []
        self.assertEqual(sql.target_for(row["state"], row["options"])[0], expected)
        for sample in self.rows:
            visible = json.dumps({key: sample[key] for key in ("state", "question", "kind", "options")})
            for forbidden in ("reference_result", "candidate_results", "target_basis", "provenance", "source_instance_id"):
                self.assertNotIn(forbidden, visible)

    def test_database_and_structural_families_are_split_disjoint(self):
        for key in ("database_sha256", "structural_family", "source_instance_id", "context_sha256"):
            registry = defaultdict(set)
            for row in self.rows:
                registry[row["metadata"][key]].add(row["split"])
            self.assertTrue(all(len(splits) == 1 for splits in registry.values()))
        ood = {json.dumps(row["metadata"]["layout"], sort_keys=True) for row in self.rows if row["split"] == "ood"}
        train = {json.dumps(row["metadata"]["layout"], sort_keys=True) for row in self.rows if row["split"] == "train"}
        self.assertFalse(ood & train)

    def test_reproducible_no_input_files_and_non_overwriting_build(self):
        with patch("builtins.open", side_effect=AssertionError("Unexpected external input read")):
            self.assertEqual(self.rows, list(sql.generate(groups_per_family=1)))
        with tempfile.TemporaryDirectory() as temp:
            first = sql.build_dataset(Path(temp) / "first", groups_per_family=1)
            second = sql.build_dataset(Path(temp) / "second", groups_per_family=1)
            self.assertEqual(first, second)
            with self.assertRaises(ValueError):
                sql.build_dataset(Path(temp) / "first", groups_per_family=1)
        for count in (0, 257):
            with self.assertRaises(ValueError):
                list(sql.generate(groups_per_family=count))


if __name__ == "__main__":
    unittest.main()
