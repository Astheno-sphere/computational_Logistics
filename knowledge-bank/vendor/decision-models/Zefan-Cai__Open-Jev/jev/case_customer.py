"""Customer-support fan-out: source-inspired, explicitly synthetic controls.

The five triage question forms come from public TypeSafe documentation, not
the inaccessible complete query in the launch post. Churn uses a local rubric.
"""

import argparse
import copy
from collections import Counter
import hashlib
import json
from pathlib import Path
import random

from .api import compile_request
from .data import SPLITS, split_group, validate_records


VERSION = "customer-control-v1"
DOC_SOURCE = "https://docs.typesafe.ai/patterns/fan-out.md"
POST_SOURCE = "https://x.com/CompleteSkeptic/status/2099925682726002904"
CATEGORIES = ("bug_report", "billing", "feature_request", "account")


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def question_definitions():
    """Documented names/forms, with operational rules added for local labels."""
    return {
        "category": {
            "type": "choice",
            "instructions": "Determine the broad category of this support ticket. For this controlled task, select the customer's expressly prioritized request. If two requests explicitly have equal priority, allocate equal support to their two categories. A malfunction of an existing feature is bug_report; a payment or refund request is billing; a request for absent functionality is feature_request; an access or profile request is account. Secondary context does not override an explicit priority.",
            "criteria": {
                "bug_report": "The user is reporting something that is broken or producing errors",
                "billing": "Charges, invoices, refunds, subscriptions",
                "feature_request": "The user is requesting new functionality",
                "account": "Login, permissions, profile, security",
            },
        },
        "bug_severity": {
            "type": "score",
            "instructions": "How severe is the reported issue? Use the stated functional impact and the existence of a workaround. Use no functional impact when no malfunction is described. In this synthetic control, if a broken feature is described but the availability of a workaround is explicitly unknown, the two latent possibilities (workaround exists; no workaround exists) are equally likely.",
            "criteria": ["Cosmetic; no impact to functionality", "Broken or degraded feature; workaround exists", "Blocking issue; no workaround exists"],
        },
        "has_reproducible_steps": {
            "type": "noul",
            "instructions": "The user describes specific steps to reproduce the issue. For this controlled task, require at least two ordered user actions and the observed result. A vague report, a resolved historical issue, or an instruction to support staff is insufficient.",
        },
        "refund_requested": {
            "type": "noul",
            "instructions": "The user is explicitly asking for a refund or credit for the current issue. A question about charges, an explicit denial of wanting money back, or a mention of an already completed refund is not a current request.",
        },
        "frustration": {
            "type": "score",
            "instructions": "How frustrated the user appears. Use the current expressed tone. For a reaction that carries no clear emotional valence, the controlled generator has two equally likely latent readings: calm or frustrated but civil. Do not infer very angry without an explicit anger signal.",
            "criteria": ["Calm, matter-of-fact", "Frustrated but civil", "Very angry"],
        },
        "churn_likelihood_level": {
            "type": "score",
            "instructions": "Churn likelihood level. This is a local ordinal intention rubric, not an empirically calibrated prediction of future churn. Evaluate the customer's stated continuation intent. If intent was explicitly withheld or not discussed, the synthetic generator has three equally likely latent intention levels.",
            "criteria": [
                "The customer explicitly intends to keep using the service and continue their subscription.",
                "The customer is undecided about continuing, or makes departure conditional on whether the issue is resolved.",
                "The customer explicitly requests cancellation or states a definite decision to stop using the service.",
            ],
        },
    }


# OOD uses separate complete utterances as well as separate dialogue envelopes.
# Natural-language signals expose observations, never the latent label fields.
UTTERANCES = {
    "id": {
        "bug": ["The report heading is misaligned, but every report function still works.",
                "Exporting a report fails, but I can download the CSV and finish in the desktop app.",
                "Report export fails through every available method, so I cannot complete my filing."],
        "bug_unknown": "Exporting a report fails. I haven't tested the desktop route and don't know whether an alternative works.",
        "billing": "My card was charged twice for the same monthly invoice.",
        "feature_request": "I would like an offline reading mode, which this product does not currently offer.",
        "account": "I need access restored after changing the email address used to sign in.",
        "repro_yes": "I open a saved report, then click Export; the download panel disappears and nothing is saved.",
        "repro_cosmetic": "I open a saved report, then click Preview; the heading shifts to the left, but all content remains readable and the report saves correctly.",
        "repro_no": "It happens sometimes, but I cannot recall the sequence that led to it.",
        "refund_yes": ["Please refund the duplicate charge to my card.", "Please apply a credit for the extra payment to my next invoice."],
        "refund_no": ["Please explain this charge; I am not asking for money back.", "Last month's refund has arrived. Today I only want the invoice explained."],
        "tone": ["Thanks for checking. I am simply reporting what I observed.",
                 "This is frustrating, but I appreciate your help and will keep this constructive.",
                 "I am furious. This treatment is outrageous and completely unacceptable!"],
        "tone_unknown": "Well, that was something.",
        "churn": ["I will keep using the service and renew my subscription.",
                  "Whether I renew depends on whether this is fixed before Friday.",
                  "I have decided to leave. Please cancel my subscription at the end of this month."],
        "churn_unknown": "We have not discussed whether I intend to renew, and I am not stating that intention now.",
        "chinese": "客户补充：我的账号名是 {entity}，上面说的是今天遇到的情况。",
    },
    "ood": {
        "bug": ["Only the spacing in the statement title looks wrong; I can still perform every operation.",
                "The statement generator is broken. Downloading the raw file and using the older client lets me finish the job.",
                "The statement cannot be generated, the older client also fails, and there is no other way to complete the job."],
        "bug_unknown": "Statement generation is broken. Nobody has established whether the older client offers a way around the problem.",
        "billing": "There are two settled debits for one membership period on my bank statement.",
        "feature_request": "Could you add a way to annotate documents without a connection? That capability does not exist yet.",
        "account": "After our administrator changed my sign-in identity, I need the permissions on my profile restored.",
        "repro_yes": "First I select a stored statement. Next I press Generate. The dialog then vanishes without creating a file.",
        "repro_cosmetic": "First I select a stored statement. Next I open its preview. The title is indented strangely, while every value remains legible and saving works.",
        "repro_no": "The fault comes and goes; I have no sequence of actions to provide.",
        "refund_yes": ["Return the second debit to the original payment method, please.", "I request an account credit equal to that duplicate payment."],
        "refund_no": ["I only seek an explanation of the debit, not reimbursement.", "A previous reimbursement was completed; this message asks only for clarification of today's statement."],
        "tone": ["I am sending these observations neutrally. Thank you for taking a look.",
                 "I am annoyed by the delay, though I remain respectful and want to work with you.",
                 "Your handling of this has made me extremely angry. I am absolutely livid!"],
        "tone_unknown": "That was certainly an experience.",
        "churn": ["My plan is to remain a subscriber and carry on using this product.",
                  "I have not decided to stay; I may move elsewhere if the problem persists.",
                  "End my membership at its next boundary. My decision to switch away is final."],
        "churn_unknown": "My future membership plans were not part of this exchange, and I decline to disclose them here.",
        "chinese": "用户附言：请按账号 {entity} 查询；本次描述仅针对现在的问题。",
    },
}


def _sample_control(rng):
    ambiguity = rng.choice(["none"] * 7 + ["category", "bug_severity", "frustration", "churn_likelihood_level"])
    category = rng.choice(CATEGORIES)
    categories = [category]
    if ambiguity == "category":
        categories.append(rng.choice([name for name in CATEGORIES if name != category]))
    elif ambiguity == "bug_severity":
        categories = ["bug_report"]
    has_bug = "bug_report" in categories
    return {"categories": categories, "ambiguity": ambiguity,
            "severity": rng.choice([1, 2]) if ambiguity == "bug_severity" else rng.randrange(3) if has_bug else 0,
            "repro": has_bug and rng.random() < 0.5,
            "refund": "billing" in categories and rng.random() < 0.5,
            "frustration": rng.randrange(2) if ambiguity == "frustration" else rng.randrange(3), "churn": rng.randrange(3)}


def latent_targets(control):
    """Exact marginal labels under explicitly defined uniform latent sets."""
    def marginal(levels, length):
        return [levels.count(index) / len(levels) for index in range(length)]

    ambiguous = control["ambiguity"]
    return {
        "category": {name: float(name in control["categories"]) / len(control["categories"]) for name in CATEGORIES},
        "bug_severity": marginal([1, 2] if ambiguous == "bug_severity" else [control["severity"]], 3),
        "has_reproducible_steps": [float(not control["repro"]), float(control["repro"])],
        "refund_requested": [float(not control["refund"]), float(control["refund"])],
        "frustration": marginal([0, 1] if ambiguous == "frustration" else [control["frustration"]], 3),
        "churn_likelihood_level": marginal([0, 1, 2] if ambiguous == "churn_likelihood_level" else [control["churn"]], 3),
    }


def _dialogue(control, rng, entity, ood, bilingual, envelope):
    bank = UTTERANCES["ood" if ood else "id"]
    issues = []
    for category in control["categories"]:
        if category == "bug_report":
            issues.append(bank["bug_unknown"] if control["ambiguity"] == "bug_severity" else bank["bug"][control["severity"]])
        else:
            issues.append(bank[category])
    if len(issues) == 2:
        priority = "Both of those requests matter equally to me; I have not chosen one to address first." if not ood else "Neither of these two requests takes precedence; they have equal priority."
    else:
        priority = "That is the request I want you to handle first." if not ood else "Please treat that request as my first priority."
    details = []
    if "bug_report" in control["categories"]:
        if control["repro"]:
            details.append(bank["repro_cosmetic"] if control["severity"] == 0 else bank["repro_yes"])
        else:
            details.append(bank["repro_no"])
    if "billing" in control["categories"]:
        details.append(rng.choice(bank["refund_yes"] if control["refund"] else bank["refund_no"]))
    details.append(bank["tone_unknown"] if control["ambiguity"] == "frustration" else bank["tone"][control["frustration"]])
    details.append(bank["churn_unknown"] if control["ambiguity"] == "churn_likelihood_level" else bank["churn"][control["churn"]])
    if bilingual:
        details.append(bank["chinese"].format(entity=entity))
    if ood:
        if envelope == 0:
            return f"Visitor {entity}: {' '.join(issues)} {priority}\nSpecialist: Describe any other observations relevant to this conversation.\nVisitor: {' '.join(details)}"
        return f"Help-desk exchange for member {entity}.\nMember wrote: {' '.join(issues)} {priority}\nSupport replied: What else should we know?\nMember replied: {' '.join(details)}"
    if envelope == 0:
        return f"Customer {entity}: {' '.join(issues)} {priority}\nAgent: Could you add the details?\nCustomer: {' '.join(details)}"
    return f"Conversation with account holder {entity}.\nCustomer message: {' '.join(issues)} {priority}\nSupport: Please tell us more.\nCustomer response: {' '.join(details)}"


def generate_cases(groups=1000, seed=42):
    if groups < 1:
        raise ValueError("groups must be positive")
    for index in range(groups):
        group = f"{VERSION}:{seed}:{index}"
        rng = random.Random(int(_digest(group), 16))
        ood = index % 10 == 0
        split = "ood" if ood else split_group(group, seed)
        control = _sample_control(rng)
        entity = ("Cedar-" if ood else "Harbor-") + _digest([group, "entity"])[:10]
        bilingual, envelope = rng.random() < 0.15, rng.randrange(2)
        state = _dialogue(control, rng, entity, ood, bilingual, envelope)
        questions = question_definitions()
        candidate_order = list(questions["category"]["criteria"].items())
        rng.shuffle(candidate_order)
        questions["category"]["criteria"] = dict(candidate_order)
        exact = latent_targets(control)
        compiled = compile_request(state, questions)
        targets = {}
        records = []
        for item in compiled:
            question_id = item["id"]
            target = [exact[question_id][key] for key in item["answer_keys"]] if item["kind"] == "choice" else exact[question_id]
            targets[question_id] = target
            metadata = {
                "family": {"choice": "routing", "score": "rubric", "noul": "evidence"}[item["kind"]],
                "case_name": "customer_support_fanout_control", "question_id": question_id,
                "template_id": f"{VERSION}:{'ood' if ood else 'id'}:{envelope}", "entity_ids": [entity],
                "language": "en+zh" if bilingual else "en", "control_latents": copy.deepcopy(control),
                "target_basis": "defined_uniform_latent_worlds" if control["ambiguity"] == question_id else "explicit_control_rule",
                "source_relation": "launch_post_name_only_local_rubric" if question_id == "churn_likelihood_level" else "public_docs_question_form_with_local_control_rules",
                "provenance": {"type": "synthetic", "generator_version": VERSION, "seed": seed,
                               "group_index": index, "variant": 0, "license": "Generated conversations: CC0-1.0; upstream question descriptions: TypeSafe documentation, license not verified",
                               "split_policy": "reserved_ood_dialogue_families_then_group_sha256_v1",
                               "source_url": POST_SOURCE if question_id == "churn_likelihood_level" else DOC_SOURCE,
                               "annotation_status": "synthetic_control_not_official_labels"},
            }
            if item["kind"] == "score":
                metadata["score_values"] = [0, 1, 2]
            records.append({"id": f"{group}:{question_id}", "group_id": group, "split": split,
                            "source": VERSION, "state": state, "question": item["question"], "kind": item["kind"],
                            "options": item["options"], "target": target, "metadata": metadata})
        workflow = {"group_id": group, "split": split, "state": state, "questions": questions, "targets": targets}
        yield workflow, records


def build_dataset(output_dir, groups=1000, seed=42):
    cases = list(generate_cases(groups, seed))
    records = [row for _, rows in cases for row in rows]
    summary = validate_records(records)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    file_checksums = {}
    for split in SPLITS:
        path = output / f"{split}.jsonl"
        path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in records if row["split"] == split), encoding="utf-8")
        file_checksums[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    workflow_path = output / "workflow_cases.jsonl"
    # Preserve criteria insertion order: each target vector follows compile_request.
    workflow_path.write_text("".join(json.dumps(workflow, ensure_ascii=False) + "\n" for workflow, _ in cases), encoding="utf-8")
    file_checksums[workflow_path.name] = hashlib.sha256(workflow_path.read_bytes()).hexdigest()
    manifest = {"schema_version": 1, "dataset": VERSION, "groups": groups, "seed": seed,
                "summary": summary, "workflow_cases": workflow_path.name, "files_sha256": file_checksums,
                "model_input_fields": ["state", "question", "kind", "options"],
                "question_counts": dict(Counter(row["metadata"]["question_id"] for row in records)),
                "source_status": "Five official-public-docs forms plus a local churn rubric; not the launch post's complete inaccessible query; all labels are synthetic controls."}
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--groups", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    print(json.dumps(build_dataset(args.output_dir, args.groups, args.seed), indent=2))


if __name__ == "__main__":
    main()
