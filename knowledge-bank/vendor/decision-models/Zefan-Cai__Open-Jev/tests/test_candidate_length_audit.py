import unittest

from scripts.audit_candidate_lengths import LengthStats


class CandidateLengthStatsTests(unittest.TestCase):
    def test_limits_count_rows_and_sequences_with_strict_exceeds_semantics(self):
        stats = LengthStats([4, 8])
        row = {"id": "a", "source": "synthetic", "kind": "choice", "split": "train"}
        stats.add(row, [4, 5, 9])
        stats.add({**row, "id": "b", "kind": "noul"}, [2])
        result = stats.report()
        self.assertEqual(result["rows"], 2)
        self.assertEqual(result["candidate_sequences"], 4)
        self.assertEqual(result["input_tokens"], 20)
        self.assertEqual(result["over_limits"], {"4": {"rows": 1, "candidate_sequences": 2},
                                                 "8": {"rows": 1, "candidate_sequences": 1}})
        self.assertEqual(result["padded_tokens_if_each_row_encoded_separately"], 29)
        self.assertEqual(result["largest_padded_row"]["candidate_sequences"], 3)
        self.assertEqual(result["longest_candidate"]["candidate_index"], 2)
        self.assertEqual(result["percentiles_nearest_rank"], {"50": 4, "90": 9, "95": 9, "99": 9})

    def test_largest_fanout_is_not_necessarily_longest_sequence(self):
        stats = LengthStats([16])
        row = {"id": "long", "source": "synthetic", "kind": "choice", "split": "ood"}
        stats.add(row, [15, 16])
        stats.add({**row, "id": "wide"}, [10] * 8)
        result = stats.report()
        self.assertEqual(result["longest_candidate"]["id"], "long")
        self.assertEqual(result["largest_padded_row"]["id"], "wide")
        self.assertEqual(result["max_candidate_sequences_per_row"], 8)
        self.assertEqual(result["over_limits"]["16"]["rows"], 0)


if __name__ == "__main__":
    unittest.main()
