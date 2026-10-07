import random
import unittest

from llm2jev.backend.sglang.prefix_plan import staged_batches


class PrefixPlanTests(unittest.TestCase):
    def assert_minimal_prefill(self, inputs):
        batches = staged_batches(inputs)
        self.assertEqual(sorted(i for batch in batches for i in batch), list(range(len(inputs))))
        cached, computed = set(), 0
        for batch in batches:
            self.assertTrue(batch)
            added = set()
            for index in batch:
                tokens = inputs[index]
                prefixes = {tuple(tokens[:end]) for end in range(1, len(tokens))}
                computed += 1 + len(prefixes - cached)
                added.update(prefixes)
            cached.update(added)
        self.assertEqual(computed, len(inputs) + len(cached))
        return batches

    def test_two_level_sharing_seeds_each_branch_before_its_leaves(self):
        inputs = [[1, 2, q, 4, c, 9] for q in (10, 20, 30) for c in (5, 6, 7)]
        self.assertEqual(self.assert_minimal_prefill(inputs), [[0], [1, 2, 3, 6], [4, 5, 7, 8]])

    def test_disjoint_inputs_and_singletons_need_one_submission(self):
        for inputs in ([[1, 2, 3], [4, 5, 6], [7]], [[1, 2, 3]], [[1], [1]]):
            with self.subTest(inputs=inputs):
                self.assertEqual(self.assert_minimal_prefill(inputs), [list(range(len(inputs)))])
        self.assertEqual(staged_batches([]), [])

    def test_duplicate_and_strict_prefix_inputs_keep_all_scoring_positions(self):
        for inputs in (
            [[1, 2, 3], [1, 2, 3], [1, 2, 3]],
            [[1, 2], [1, 2, 3, 4], [1, 2, 3], [1]],
            [[1, 2, 3, 4], [1, 2], [1, 2, 3], [1]],
        ):
            with self.subTest(inputs=inputs):
                self.assert_minimal_prefill(inputs)

    def test_nested_branches_and_permutations_reach_unique_prefix_bound(self):
        rng = random.Random(42)
        for _ in range(200):
            inputs = [[rng.randrange(3) for _ in range(rng.randrange(1, 12))]
                      for _ in range(rng.randrange(1, 25))]
            self.assert_minimal_prefill(inputs)
            rng.shuffle(inputs)
            self.assert_minimal_prefill(inputs)


if __name__ == "__main__":
    unittest.main()
