"""Independent policy replay and boundary/scope tests for the original candidate."""
from collections import Counter, defaultdict
import copy
import itertools
from pathlib import Path
import tempfile
import unittest

from jev.policy_controls_v6 import FAMILIES, audit, build, oracle, records


def independent_answer(family, state):
    """Separate decision-table/event-fold expression; no generator oracle calls."""
    if family == "explicit_refund_priority":
        facts = state["verified_case"]
        eligible = facts["defect_confirmed"] or facts["seal_intact"]
        table = {
            (True, False, False): "recall remediation", (True, False, True): "recall remediation",
            (True, True, False): "recall remediation", (True, True, True): "recall remediation",
            (False, False, False): "reject request", (False, False, True): "reject request",
            (False, True, False): "reject request",
            (False, True, True): ("automatic reimbursement", "review reimbursement")[
                int(facts["amount_cents"] > state["trusted_policy"]["automatic_limit_cents"])],
        }
        return table[facts["verified_recall"], facts["receipt_verified"], eligible]
    if family == "scoped_joint_approval":
        q = state["request"]
        scope = tuple(q[k] for k in ("resource", "operation", "currency"))
        latest = {}
        for e in sorted(state["signed_events"], key=lambda x: x["sequence"]):
            credential = e["credential_scope"]
            matches = (set(credential) == {"resource", "operation", "currency"}
                       and tuple(credential[k] for k in ("resource", "operation", "currency")) == scope
                       and (e["resource"], e["operation"]) == scope[:2])
            if matches and e["verified_signature"] and e["issuer_role"] in state["trusted_policy"]["required_roles"]:
                latest[e["issuer_role"]] = e
        failed = [
            (0, "reject revoked consent", "revoke" in {e["status"] for e in latest.values()}),
            (1, "request missing consent", set(latest) != set(state["trusted_policy"]["required_roles"])),
            (2, "request higher capacity", any(e["capacity_cents"] < q["amount_cents"] for e in latest.values())),
            (3, "execute", True),
        ]
        return min((priority, label) for priority, label, applies in failed if applies)[1]
    q = state["request"]
    valid = [p for p in state["signed_policy_registry"] if
             (p["issuer_role"], p["department"], p["credential_scope"], p["verified_signature"])
             == (state["policy_authority"], q["department"], q["department"], True)]
    ordered = sorted(valid, key=lambda p: p["revision"], reverse=True)
    if not ordered or ordered[0]["status"] == "withdrawn":
        return "verify policy"
    table = {(True, True): "fraud review", (True, False): "fraud review",
             (False, True): "automatic processing", (False, False): "capacity review"}
    return table[q["confirmed_fraud"], q["amount_cents"] <= ordered[0]["automatic_limit_cents"]]


class PolicyControlsV6Test(unittest.TestCase):
    def test_all_384_targets_independent_replay_and_group_isolation(self):
        rows = list(records())
        self.assertEqual(rows, list(records()))
        self.assertEqual(len(rows), 384)
        groups, answers = defaultdict(set), defaultdict(list)
        for row in rows:
            family = row["metadata"]["scenario_family"]
            answer = independent_answer(family, row["state"])
            answers[row["group_id"]].append(answer)
            expected = ("yes" if answer == row["metadata"]["proposed_outcome"] else "no") if row["kind"] == "noul" else answer
            self.assertEqual(row["options"][row["target"].index(1.0)], expected)
            self.assertNotIn("/train/", str(row["state"]))
            self.assertEqual(row["metadata"]["provenance"]["upstream_rows_imported"], 0)
            groups[row["group_id"]].add(row["split"])
        self.assertEqual(len(groups), 96)
        self.assertTrue(all(len(s) == 1 for s in groups.values()))
        self.assertTrue(all(len(set(a)) >= 2 for a in answers.values()))
        self.assertEqual(audit(rows)["splits"], {"train": 240, "calibration": 36, "validation": 36, "test": 36, "ood": 36})
        positions = defaultdict(Counter)
        for r in rows:
            if r["kind"] == "choice":
                positions[r["split"], r["metadata"]["scenario_family"]][r["target"].index(1.0)] += 1
        self.assertTrue(all(max(c.values()) - min(c.values()) <= 1 for c in positions.values()))

    def test_refund_priority_exhaustive_48_boundary_cases(self):
        state = next(r["state"] for r in records() if r["metadata"]["scenario_family"] == FAMILIES[0])
        for recall, receipt, defect, seal, difference in itertools.product((False, True), (False, True), (False, True), (False, True), (-1, 0, 1)):
            c = copy.deepcopy(state)
            c["verified_case"].update(verified_recall=recall, receipt_verified=receipt, defect_confirmed=defect,
                                      seal_intact=seal, amount_cents=c["trusted_policy"]["automatic_limit_cents"] + difference)
            self.assertEqual(oracle(FAMILIES[0], c), independent_answer(FAMILIES[0], c))
            self.assertIs(type(c["verified_case"]["amount_cents"]), int)

    def test_latest_signature_scope_revocation_and_one_cent(self):
        state = next(r["state"] for r in records() if r["metadata"]["scenario_family"] == FAMILIES[1])
        self.assertEqual(oracle(FAMILIES[1], state), "execute")
        state["signed_events"].reverse()
        self.assertEqual(oracle(FAMILIES[1], state), "execute")
        state["request"]["amount_cents"] += 1
        self.assertEqual(oracle(FAMILIES[1], state), "request higher capacity")
        state["request"]["amount_cents"] -= 1
        role = state["trusted_policy"]["required_roles"][0]
        signed = next(e for e in state["signed_events"] if e["issuer_role"] == role and e["sequence"] == 5)
        for field in ("resource", "operation", "currency"):
            c = copy.deepcopy(state)
            e = next(x for x in c["signed_events"] if x["issuer_role"] == role and x["sequence"] == 5)
            e["credential_scope"][field] += "-wrong"
            self.assertEqual(oracle(FAMILIES[1], c), "request missing consent")
        state["signed_events"].append({**copy.deepcopy(signed), "sequence": 50, "status": "revoke"})
        self.assertEqual(oracle(FAMILIES[1], state), "reject revoked consent")
        state["signed_events"].append({**copy.deepcopy(signed), "sequence": 51})
        self.assertEqual(oracle(FAMILIES[1], state), "execute")
        state["signed_events"].append({**copy.deepcopy(signed), "sequence": 51, "status": "revoke"})
        with self.assertRaisesRegex(ValueError, "Conflicting signed sequence"):
            oracle(FAMILIES[1], state)

    def test_untrusted_text_invariance_and_signed_policy_withdrawal(self):
        rows = [r for r in records() if r["metadata"]["scenario_family"] == FAMILIES[2]]
        groups = defaultdict(list)
        for row in rows:
            groups[row["group_id"]].append(row)
        for variants in groups.values():
            answers = [independent_answer(FAMILIES[2], r["state"]) for r in variants]
            self.assertEqual(answers, ["automatic processing", "automatic processing", "capacity review", "fraud review"])
        c = copy.deepcopy(rows[0]["state"])
        current = next(p for p in c["signed_policy_registry"] if p["revision"] == 7)
        current["status"] = "withdrawn"
        self.assertEqual(oracle(FAMILIES[2], c), "verify policy")
        c["request"]["confirmed_fraud"] = True
        self.assertEqual(oracle(FAMILIES[2], c), "verify policy")
        c["signed_policy_registry"] = [p for p in c["signed_policy_registry"] if not p["verified_signature"]]
        self.assertEqual(oracle(FAMILIES[2], c), "verify policy")

    def test_corrupted_target_incomplete_group_and_frozen_output(self):
        rows = list(records())
        r = rows[0]
        old = r["target"].index(1.0)
        r["target"] = [float(i == (old + 1) % 4) for i in range(4)]
        with self.assertRaisesRegex(ValueError, "Oracle disagrees"):
            audit(rows)
        with self.assertRaisesRegex(ValueError, "four variants"):
            audit(list(records())[1:])
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "candidate"
            manifest = build(output)
            self.assertEqual(manifest["summary"]["groups"], 96)
            with self.assertRaises(FileExistsError):
                build(output)


if __name__ == "__main__":
    unittest.main()
