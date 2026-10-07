import copy
import unittest

from scripts.audit_community_diversity_v2 import independent_decision, interpret, parse_visible_rule


class IndependentVisibleRulesTest(unittest.TestCase):
    def test_boolean_truth_tables_and_unknown_comparisons(self):
        domain = (False, None, True)
        and_table = ((False, False, False), (False, None, None), (False, None, True))
        or_table = ((False, None, True), (None, None, True), (True, True, True))
        implication = ((True, True, True), (None, None, True), (False, None, True))
        for i, left in enumerate(domain):
            for j, right in enumerate(domain):
                facts = {"left": left, "right": right}
                for rule, expected in (("(left AND right)", and_table[i][j]),
                                       ("(left OR right)", or_table[i][j]),
                                       ("IF (left) THEN (right)", implication[i][j])):
                    self.assertIs(interpret(parse_visible_rule(rule), facts), expected)
        self.assertIsNone(interpret(parse_visible_rule("(missing equals missing)"), {}))
        self.assertIsNone(interpret(parse_visible_rule("NOT (missing)"), {}))

    def test_nested_arithmetic_sets_and_quoted_literals(self):
        examples = [
            ('((count times multiplier) equals total)', {"count": 7, "multiplier": 3, "total": 21}, True),
            ('(absolute value of ((first - second)) <= 2)', {"first": 5, "second": 8}, False),
            ('(fields contains "source details")', {"fields": ["source details", "date"]}, True),
            ('(mime is a member of ["text/plain", "application/pdf"])', {"mime": "application/pdf"}, True),
            ('IF ((hazard equals true)) THEN ((specialist equals true))', {"hazard": True, "specialist": False}, False),
            ('((start < end) AND NOT ((withdrawn equals true)))', {"start": 10, "end": 10, "withdrawn": False}, False),
        ]
        for text, facts, expected in examples:
            self.assertIs(interpret(parse_visible_rule(text), facts), expected)
        with self.assertRaises(ValueError):
            parse_visible_rule('(a equals 1); arbitrary code')

    def test_independent_end_to_end_choice_probe_and_target_corruption(self):
        state = {"numbered_requirements": ['(value >= 4)', '(region equals "west")', '(active equals true)', 'NOT ((withdrawn equals true))'],
                 "selection_rule": "Among fully supported candidates choose the largest revision; if tied choose the lexicographically smallest candidate ID. If none is fully supported choose abstain.",
                 "candidates": {"B": {"value": 4, "region": "west", "active": True, "withdrawn": False, "revision": 9},
                                "A": {"value": 4, "region": "west", "active": True, "withdrawn": False, "revision": 9},
                                "C": {"value": 5, "region": "west", "active": None, "withdrawn": False, "revision": 10}}}
        row = {"state": state, "kind": "choice", "question": "Select.", "options": ["C", "abstain", "B", "A"], "target": [0., 0., 0., 1.]}
        self.assertEqual(independent_decision(row)["winner"], "A")
        row.update(kind="noul", question="Candidate C. Is it established?", options=["no", "yes"], target=[1., 0.])
        independent_decision(row)
        row.update(kind="score", question="Candidate C. Count.", options=[f"Exactly {n} of the 4 numbered requirements are established." for n in range(5)], target=[0., 0., 0., 1., 0.])
        independent_decision(row)
        wrong = copy.deepcopy(row)
        wrong["target"] = [0., 0., 0., 0., 1.]
        with self.assertRaisesRegex(ValueError, "target mismatch"):
            independent_decision(wrong)


if __name__ == "__main__":
    unittest.main()
