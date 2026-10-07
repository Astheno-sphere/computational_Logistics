import json
import unittest

from jev.api import candidate_prompts
from jev.case_wikiracing import (
    decode_title, distances_to, records_from_graph, replay_human_path,
    sample_candidates, shortest_path,
)
from jev.data import validate_records


def human_pair(source, target, path=None):
    tokens = path or [source, target]
    return {"source": source, "target": target, "human_path": tokens,
            "human_replayed_path": replay_human_path(tokens),
            "human_forward_edges_missing_from_graph": [],
            "original_id": f"fixture:{source}:{target}"}


class WikiCaseTest(unittest.TestCase):
    def test_reverse_bfs_is_directed_and_leaves_unreachable_absent(self):
        graph = {"A": ["B", "C"], "B": ["D", "C"], "C": ["D", "A"],
                 "D": ["A", "B", "E"], "E": []}
        distances = distances_to(graph, "D")
        self.assertEqual(distances, {"D": 0, "B": 1, "C": 1, "A": 2})
        self.assertEqual(shortest_path(graph, "A", "D", distances), ["A", "B", "D"])
        with self.assertRaises(ValueError):
            shortest_path(graph, "E", "D", distances)

    def test_browser_back_replays_navigation_stack(self):
        path = ["A", "B", "C", "<", "<", "D"]
        self.assertEqual(replay_human_path(path), ["A", "B", "C", "B", "A", "D"])
        for invalid in ([], ["<"], ["A", "<"], ["A", ""]):
            with self.assertRaises(ValueError):
                replay_human_path(invalid)

    def test_path_separators_are_split_before_title_decoding(self):
        tokens = [decode_title(token) for token in "Start;Semi%3Bcolon;<;New_York_City".split(";")]
        self.assertEqual(tokens, ["Start", "Semi;colon", "<", "New York City"])
        self.assertEqual(replay_human_path(tokens), ["Start", "Semi;colon", "Start", "New York City"])

    def test_policy_ties_are_uniform_over_best_candidates(self):
        graph = {"A": ["B", "C"], "B": ["D", "C"], "C": ["D", "A"], "D": ["A", "B"]}
        rows, workflows, stats = records_from_graph(graph, [human_pair("A", "D", ["A", "B", "D"])])
        validate_records(rows)
        self.assertEqual(rows[0]["target"], [.5, .5])
        self.assertEqual(rows[0]["metadata"]["candidate_shortlist_excess_steps"], 0)
        self.assertEqual(stats["full_best_coverage"]["fraction"], 1)
        self.assertEqual(workflows[0]["full_outlinks"], graph["A"])
        self.assertEqual(workflows[0]["expert_path"], ["A", "B", "D"])

    def test_candidates_do_not_change_with_hidden_distances_or_human_trace(self):
        links = ["B", "C", "D", "E"]
        selected = sample_candidates(links, "A", max_candidates=2)
        omitted = next(page for page in links if page not in selected)
        graph = {"A": links, **{page: ["J"] for page in links}, "J": ["T"], "T": []}
        first, _, _ = records_from_graph(graph, [human_pair("A", "T", ["A", "B", "J", "T"])], max_candidates=2)
        graph[omitted] = ["T"]
        second, _, stats = records_from_graph(graph, [human_pair("A", "T", ["A", omitted, "T"])], max_candidates=2)
        self.assertEqual(first[0]["options"], second[0]["options"])
        self.assertEqual(first[0]["state"], second[0]["state"])
        self.assertNotIn(omitted, second[0]["options"])
        self.assertFalse(second[0]["metadata"]["shortlist_contains_full_best"])
        self.assertEqual(second[0]["metadata"]["candidate_shortlist_excess_steps"], 1)
        self.assertEqual(second[0]["target"], [.5, .5])
        self.assertEqual(stats["full_best_coverage"]["covered"], 0)
        self.assertEqual(sample_candidates(list(reversed(links)), "A", max_candidates=2), selected)

    def test_all_unreachable_candidates_are_filtered_without_gold_insertion(self):
        links = ["B", "C", "D", "E"]
        selected = sample_candidates(links, "A", max_candidates=2)
        omitted = next(page for page in links if page not in selected)
        graph = {"A": links, **{page: [] for page in links}, "T": []}
        graph[omitted] = ["T"]
        rows, workflows, stats = records_from_graph(
            graph, [human_pair("A", "T", ["A", omitted, "T"])], max_candidates=2)
        self.assertEqual(rows, [])
        self.assertEqual(workflows, [])
        self.assertEqual(stats["selected_human_pairs"], 1)
        self.assertEqual(stats["all_candidates_unreachable_filtered"], 1)
        self.assertIsNone(stats["full_best_coverage"]["fraction"])

    def test_unreachable_option_is_zero_and_distance_stays_metadata(self):
        graph = {"A": ["B", "C"], "B": ["T"], "C": [], "T": []}
        rows, _, _ = records_from_graph(graph, [human_pair("A", "T", ["A", "B", "T"])])
        row = rows[0]
        self.assertEqual(dict(zip(row["options"], row["target"])), {"B": 1.0, "C": 0.0})
        self.assertEqual(row["metadata"]["candidate_distances"], {"B": 1, "C": None})
        prompts = json.dumps(candidate_prompts(row))
        for hidden in ("candidate_distances", "full_shortest_path_length", "human_path", "expert_path", "fixture:"):
            self.assertNotIn(hidden, prompts)

    def test_target_isolation_determinism_and_workflow_paths(self):
        nodes = [f"Page {i:02}" for i in range(40)]
        graph = {page: [nodes[(i + step) % len(nodes)] for step in (1, 2, 3)]
                 for i, page in enumerate(nodes)}
        pairs = []
        for target in nodes:
            distances = distances_to(graph, target)
            for source in nodes:
                if source != target:
                    pairs.append(human_pair(source, target, shortest_path(graph, source, target, distances)))
        first = records_from_graph(graph, pairs, targets=30, pairs_per_target=4, max_candidates=2)
        second = records_from_graph(graph, list(reversed(pairs)), targets=30, pairs_per_target=4, max_candidates=2)
        self.assertEqual(first, second)
        rows, workflows, stats = first
        summary = validate_records(rows)
        self.assertEqual(summary["records"], 120)
        self.assertEqual(summary["groups"], 30)
        self.assertEqual(stats["selected_ood_targets"], 3)
        target_splits = {}
        for row, workflow in zip(rows, workflows):
            target = row["state"]["target_page"]
            target_splits.setdefault(target, row["split"])
            self.assertEqual(target_splits[target], row["split"])
            self.assertEqual(workflow["id"], row["id"])
            self.assertEqual(set(workflow["full_outlinks"]), set(graph[workflow["source"]]))
            self.assertTrue(set(row["options"]) <= set(workflow["full_outlinks"]))
            self.assertEqual(workflow["expert_path"][0], workflow["source"])
            self.assertEqual(workflow["expert_path"][-1], target)
            self.assertEqual(len(workflow["expert_path"]) - 1, row["metadata"]["full_shortest_path_length"])
            for source, following in zip(workflow["expert_path"], workflow["expert_path"][1:]):
                self.assertIn(following, graph[source])
        self.assertEqual(len([split for split in target_splits.values() if split == "ood"]), 3)

    def test_invalid_limits_are_rejected(self):
        for kwargs in ({"targets": 0}, {"pairs_per_target": 0}, {"max_candidates": 1}):
            with self.assertRaises(ValueError):
                records_from_graph({}, [], **kwargs)
        with self.assertRaises(ValueError):
            sample_candidates(["A", "B"], "C", max_candidates=1)


if __name__ == "__main__":
    unittest.main()
