"""Build and evaluate synthetic workflow controls without using official examples."""

import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import random

from .api import compile_request, format_response
from .data import SPLITS, read_jsonl, split_group, validate_records
from .workflows import (ACTION_RULES, SOURCES, gate_actions, policy_fixture_actions,
                        policy_fixture_probabilities, policy_fixture_response,
                        select_actions, workflow_request)


VERSION = "workflow-controls-v1"


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _customer(rng, entity, scenario, ood):
    charge, card, subscription = entity + ":charge", entity + ":card", entity + ":subscription"
    amount = rng.randint(101, 999) * (101 if ood else 10)
    operation, object_id = "refund", charge
    texts = ["Please refund this charge.", "Please freeze my card.", "Please cancel my subscription.",
             "Please connect me to a human.", "I am reporting an unauthorized charge.",
             "Everything is resolved. Thank you.", "", "I am not asking for a refund.",
             "Yes, I approve the pending proposal.", "Please refund this charge.",
             "Please refund this charge.", "Please explain what happened."]
    alternate = ["Please return the payment.", "Please block my card.", "Please end my membership.",
                 "I need to talk to a person.", "There is a payment I did not make.",
                 "All sorted. No further help needed.", "", "Do not return the payment.",
                 "Yes, proceed with the pending proposal.", "Please reimburse this charge.",
                 "Please return the payment.", "Tell me the status of this case."]
    text = (alternate if ood else texts)[scenario % len(texts)]
    if scenario % len(texts) == 1:
        operation, object_id = "freeze_card", card
    elif scenario % len(texts) == 2:
        operation, object_id = "cancel_subscription", subscription
    state = {
        "customer_record": {"display_name": entity, "prior_contact_count": rng.randrange(4)},
        "conversation": [{"role": "assistant", "text": "I can help with the account shown below."}, {"role": "customer", "id": entity + ":turn", "text": text}] if text else [],
        "identity": {"verified": True, "account_id": entity},
        "account": {"id": entity, "subscription": {"id": subscription, "status": "active"},
                    "charges": [{"id": charge, "status": "settled", "amount_cents": amount}],
                    "cards": [{"id": card, "status": "active"}], "refunds": []},
        "pending_proposal": {"id": entity + ":proposal", "operation": operation, "object_id": object_id, "amount_cents": amount},
        "consents": [{"proposal_id": entity + ":proposal", "response_message_id": entity + ":turn", "account_id": entity, "operation": operation, "object_id": object_id, "amount_cents": amount, "status": "approved"}],
        "assistant_claims": [],
    }
    if scenario % len(texts) in (3, 4, 5, 6, 7, 9, 11):
        state["consents"] = []
    if scenario % len(texts) == 10:
        state["account"]["refunds"] = [{"charge_id": charge, "amount_cents": amount, "status": "settled"}]
    if scenario % len(texts) == 11:
        state["assistant_claims"] = [{"claim": "refund_settled", "charge_id": charge, "amount_cents": amount}]
        state["conversation"][0]["text"] = "The full refund has already settled."
    return state


def _security(rng, entity, scenario, ood):
    day = rng.randrange(10000, 20000) if ood else rng.randrange(100, 500)
    patterns = [
        None, None, None,
        {"kind": "connection", "status": "active", "destination_reputation": "malicious", "reach": "organization"},
        {"kind": "connection", "status": "active", "destination_reputation": "malicious", "reach": "single"},
        {"kind": "session", "status": "active", "attribution": "compromised", "reach": "workgroup"},
        {"kind": "credentials", "exposure": "leaked", "credential_type": "cloud_access_key"},
        {"kind": "session", "status": "active", "attribution": "compromised", "reach": "single"},
        {"kind": "credentials", "exposure": "leaked", "credential_type": "password"},
        {"kind": "mail", "status": "delivered", "reputation": "malicious", "mailbox_count": 3},
        {"kind": "mail", "status": "delivered", "reputation": "malicious", "mailbox_count": 1, "evidence": "confirmed"},
        {"kind": "mail", "status": "delivered", "reputation": "malicious", "mailbox_count": 1, "evidence": "suspected"},
        {"kind": "process", "status": "running", "reputation": "malicious", "persistence": True},
        {"kind": "process", "status": "running", "reputation": "malicious", "persistence": False},
        {"kind": "file", "reputation": "malicious"},
        {"kind": "configuration", "authorization": "unauthorized", "persistence": True},
        {"kind": "unclassified", "evidence": "confirmed_malicious"},
    ]
    index = scenario % len(patterns)
    record = copy.deepcopy(patterns[index])
    state = {"alert": {"id": entity + ":alert", "asset_id": entity, "activity": "new_login" if index == 1 else "endpoint_observation", "day": day},
             "asset": {"id": entity, "environment": "production" if ood else "staging", "role": "application_server", "redundancy": "replicated", "owner": "owner-" + entity},
             "open_tickets": [], "registered_devices": [], "maintenance": [],
             "events": [dict(record, asset_id=entity)] if record else [],
             "responder_grants": [{"asset_id": entity, "operations": [action for action in ACTION_RULES["security_incidents"] if action not in ("AUTO CLOSE", "NOTIFY USER", "ESCALATE TIER2", "ESCALATE URGENT")], "status": "approved", "valid_from_day": day - 1, "valid_to_day": day + 1}]}
    if index == 0:
        state["maintenance"] = [{"asset_id": entity, "activity": "endpoint_observation", "status": "approved", "start_day": day - 1, "end_day": day + 1}]
    return state


def _agent(rng, entity, scenario, ood):
    instant = rng.randrange(10000, 20000) if ood else rng.randrange(100, 500)
    state = {"instructions": "Complete the customer's requested operation only after permission is approved. Report the actual tool result.",
             "conversation": [{"role": "customer", "text": "Please update the selected resource once my approval is recorded."}],
             "permission_grants": [{"tool": "update_record", "resource": entity, "status": "approved", "approved_at": instant - 1}],
             "tool_calls": [{"tool": "update_record", "resource": entity, "effect": "mutation", "started_at": instant, "status": "succeeded", "environment": "staging", "arguments": {"description": "Revised display text"}, "result": {"updated": True}}],
             "trace_status": "completed", "task_scope": "supported", "final_answer": "Completed successfully.", "feedback": "satisfied"}
    index = scenario % 7
    if index == 1:
        state.update(task_scope="unsupported", feedback="dissatisfied")
    elif index == 2:
        state.update(feedback="unknown")
    elif index in (3, 4, 6):
        state["tool_calls"][0].update(status="failed", failure_origin="tool", transient=False, result={"updated": False, "error": "write failed"})
        if index in (4, 6):
            state.update(feedback="dissatisfied", final_answer="The operation failed; the resource was not changed.")
        if index == 6:
            state["tool_calls"][0].update(failure_origin="platform", transient=True)
    elif index == 5:
        state["permission_grants"][0]["approved_at"] = instant + 1
    return state


def _invoice(rng, entity, scenario, ood):
    today = rng.randrange(10000, 20000) if ood else rng.randrange(100, 500)
    qty, price = rng.randrange(3, 20), rng.randrange(100, 800) * (100 if ood else 1)
    state = {"today": today, "invoice": {"number": entity + ":invoice", "vendor_id": entity, "quantity": qty, "unit_price_cents": price, "payment_account": entity + ":bank", "due_day": today},
             "vendor": {"id": entity, "verified_payment_account": entity + ":bank"},
             "purchase_order": {"id": entity + ":po", "vendor_id": entity, "quantity": qty, "unit_price_cents": price},
             "contract": {"pricing_basis": "unit price", "currency": "USD"},
             "delivery": {"order_id": entity + ":po", "quantity": qty},
             "prior_invoices": [], "correspondence": [{"sender": "vendor", "text": "Please review this invoice against the purchase order and receiving record."}],
             "approvals": [{"vendor_id": entity, "invoice_number": entity + ":invoice", "status": "approved", "max_amount_cents": qty * price, "allow_partial": True, "approved_at_day": today - 1, "valid_until_day": today + 2}]}
    index = scenario % 10
    if index == 1:
        state["invoice"]["due_day"] = today + 15
    elif index == 2:
        state["delivery"]["quantity"] = qty - 1
    elif index == 3:
        state["approvals"] = []
    elif index == 4:
        state["purchase_order"] = None
    elif index == 5:
        state["invoice"]["unit_price_cents"] += 1
    elif index == 6:
        state["invoice"]["payment_account"] = entity + ":unverified-bank"
    elif index == 7:
        state["prior_invoices"] = [{"vendor_id": entity, "invoice_number": entity + ":invoice", "status": "paid"}]
    elif index == 8:
        state["delivery"] = None
    elif index == 9:
        state["delivery"]["quantity"] = qty - 1
        state["approvals"][0]["allow_partial"] = False
    return state


GENERATORS = dict(zip(ACTION_RULES, (_customer, _security, _agent, _invoice)))


def example_state(workflow, scenario=0, seed=42, ood=False):
    if workflow not in GENERATORS:
        raise ValueError(f"unknown workflow: {workflow}")
    return GENERATORS[workflow](random.Random(seed), "Example-" + _digest([workflow, scenario, seed])[:12], scenario, ood)


def counterfactuals(workflow, state):
    """Related factual/authorization mutations stay in the same dataset group."""
    yield "observed", copy.deepcopy(state)
    no_authority = copy.deepcopy(state)
    wrong_facts = copy.deepcopy(state)
    if workflow == "customer_service":
        no_authority["consents"] = []
        wrong_facts["identity"]["account_id"] += ":other-account"
    elif workflow == "security_incidents":
        no_authority["responder_grants"] = []
        wrong_facts["asset"].update(environment="production", redundancy="single", role="domain_controller")
        for grant in wrong_facts["responder_grants"]:
            grant["valid_to_day"] = wrong_facts["alert"]["day"] - 1
    elif workflow == "agent_trace_observability":
        no_authority["permission_grants"] = []
        wrong_facts["permission_grants"][0]["resource"] += ":other-resource"
    else:
        no_authority["approvals"] = []
        wrong_facts["prior_invoices"] = [{"vendor_id": state["invoice"]["vendor_id"], "invoice_number": state["invoice"]["number"], "status": "paid"}]
    yield "without_authorization", no_authority
    yield "conflicting_record", wrong_facts


def generate_cases(groups_per_workflow=240, seed=42):
    if type(groups_per_workflow) is not int or groups_per_workflow < 1:
        raise ValueError("groups_per_workflow must be a positive integer")
    for workflow, generate in GENERATORS.items():
        for index in range(groups_per_workflow):
            group = f"{VERSION}:{workflow}:{seed}:{index}"
            rng = random.Random(int(_digest(group), 16))
            ood = index % 10 == 0
            split = "ood" if ood else split_group(group, seed)
            entity = ("Novel-" if ood else "Case-") + _digest([group, "entity"])[:16]
            scenario = index // 10 + index % 10
            original = generate(rng, entity, scenario, ood)
            for variant, (variant_name, state) in enumerate(counterfactuals(workflow, original)):
                request = workflow_request(workflow, state)
                compiled = compile_request(**request)
                targets = dict(zip(ACTION_RULES[workflow], policy_fixture_probabilities(workflow, state)))
                case_id = f"{group}:v{variant}"
                case = {"case_id": case_id, "group_id": group, "split": split, "workflow": workflow,
                        **request, "targets": targets, "reference_actions": policy_fixture_actions(workflow, state),
                        "reference_kind": "deterministic_synthetic_policy_fixture", "variant": variant_name}
                rows = []
                for item in compiled:
                    metadata = {"family": "policy", "case_name": workflow, "question_id": item["id"],
                                "entity_ids": [entity], "template_id": f"{VERSION}:{workflow}:{'ood' if ood else 'id'}",
                                "target_basis": "deterministic_local_policy_not_official_labels",
                                "provenance": {"type": "synthetic", "generator_version": VERSION, "seed": seed,
                                               "group_index": index, "variant": variant, "license": "CC0-1.0",
                                               "split_policy": "reserved_ood_ranges_and_wording_then_parent_group_sha256_v1",
                                               "source_url": SOURCES[workflow], "source_relation": "task_form_inspiration_only_no_official_examples_copied"}}
                    rows.append({"id": f"{case_id}:{item['id']}", "group_id": group, "split": split, "source": f"{VERSION}/{workflow}",
                                 "state": state, "question": item["question"], "kind": item["kind"], "options": item["options"],
                                 "target": targets[item["id"]], "metadata": metadata})
                yield case, rows


def build_dataset(output_dir, groups_per_workflow=240, seed=42):
    cases = list(generate_cases(groups_per_workflow, seed))
    records = [row for _, rows in cases for row in rows]
    summary = validate_records(records)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    checksums = {}
    for split in SPLITS:
        path = output / f"{split}.jsonl"
        path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in records if row["split"] == split))
        checksums[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    path = output / "workflow_cases.jsonl"
    path.write_text("".join(json.dumps(case, ensure_ascii=False) + "\n" for case, _ in cases))
    checksums[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    positives = Counter(f"{case['workflow']}/{action}" for case, _ in cases for action in case["reference_actions"])
    manifest = {"schema_version": 1, "dataset": VERSION, "groups_per_workflow": groups_per_workflow, "seed": seed,
                "summary": summary, "workflow_cases": len(cases), "files_sha256": checksums,
                "model_input_fields": ["state", "question", "kind", "options"], "positive_action_counts": dict(sorted(positives.items())),
                "sources": SOURCES, "official_examples_used": 0,
                "limits": "Local deterministic synthetic policy labels. OOD changes numeric ranges, entity IDs and customer wording, not real traffic. No learned quality claim."}
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return manifest


def evaluate_predictions(cases, predictions, threshold=0.5):
    """Score saved learned responses separately from post-gate action sets."""
    cases = list(cases)
    predictions = list(predictions)
    by_id = {item["case_id"]: item for item in predictions}
    if len(by_id) != len(predictions):
        raise ValueError("duplicate prediction case ID")
    if not cases or len({item["case_id"] for item in cases}) != len(cases):
        raise ValueError("cases must be nonempty with unique case IDs")
    if set(by_id) != {item["case_id"] for item in cases}:
        raise ValueError("prediction IDs must exactly match evaluated case IDs")
    counts, workflow_counts = Counter(), {}
    for case in cases:
        workflow = case["workflow"]
        prediction = by_id[case["case_id"]]
        if prediction.get("predictor_kind") != "learned":
            raise ValueError("learned evaluation rejects oracle/fixture predictions")
        expected = set(case["reference_actions"])
        raw = set(select_actions(workflow, prediction["response"], threshold))
        decision = gate_actions(workflow, case["state"], list(raw))
        gated = set(decision["allowed_actions"])
        current = Counter(cases=1, raw_exact=int(raw == expected), gated_exact=int(gated == expected),
                          true_positive=len(raw & expected), false_positive=len(raw - expected), false_negative=len(expected - raw),
                          blocked_actions=len(decision["blocked_actions"]))
        counts.update(current)
        workflow_counts.setdefault(workflow, Counter()).update(current)
    def metrics(counter):
        return {**counter, "raw_exact_match": counter["raw_exact"] / counter["cases"],
                "gated_exact_match": counter["gated_exact"] / counter["cases"],
                "micro_f1": 2 * counter["true_positive"] / max(1, 2 * counter["true_positive"] + counter["false_positive"] + counter["false_negative"])}
    return {"reference_kind": "synthetic_local_policy", "predictor_kind": "learned", "overall": metrics(counts),
            "workflows": {name: metrics(count) for name, count in workflow_counts.items()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--output-dir", required=True)
    build.add_argument("--groups-per-workflow", type=int, default=240)
    build.add_argument("--seed", type=int, default=42)
    demo = sub.add_parser("demo")
    demo.add_argument("--workflow", choices=tuple(ACTION_RULES), required=True)
    demo.add_argument("--scenario", type=int, default=0)
    demo.add_argument("--request")
    demo.add_argument("--max-length", type=int, default=4096)
    predictor = demo.add_mutually_exclusive_group(required=True)
    predictor.add_argument("--policy-fixture", action="store_true")
    predictor.add_argument("--checkpoint")
    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("--cases", required=True)
    evaluate.add_argument("--predictions", required=True)
    args = parser.parse_args()
    if args.command == "build":
        result = build_dataset(args.output_dir, args.groups_per_workflow, args.seed)
    elif args.command == "evaluate":
        predictions = list(read_jsonl(args.predictions))
        if len({item["case_id"] for item in predictions}) != len(predictions):
            raise ValueError("duplicate prediction case ID")
        result = evaluate_predictions(read_jsonl(args.cases), predictions)
    else:
        state = json.loads(Path(args.request).read_text())["state"] if args.request else example_state(args.workflow, args.scenario)
        if args.policy_fixture:
            response = policy_fixture_response(args.workflow, state)
        else:
            import torch
            from .metrics import softmax
            from .model import DecisionModel
            checkpoint = Path(args.checkpoint)
            temperature = json.loads((checkpoint / "temperature.json").read_text())["temperature"]
            records = compile_request(**workflow_request(args.workflow, state))
            if args.max_length < 1:
                raise ValueError("max length must be positive")
            model = DecisionModel.load(checkpoint)
            model.max_length = args.max_length
            with torch.inference_mode():
                logits = model(records)
            response = format_response(records, [softmax(row.float().cpu().tolist(), temperature) for row in logits])
        result = {"workflow": args.workflow, "predictor_kind": "policy_fixture_oracle" if args.policy_fixture else "learned",
                  "response": response, "decision": gate_actions(args.workflow, state, select_actions(args.workflow, response)),
                  "reference_actions": policy_fixture_actions(args.workflow, state) if args.policy_fixture else None}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
