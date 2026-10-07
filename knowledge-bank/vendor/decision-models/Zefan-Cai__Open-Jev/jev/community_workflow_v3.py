"""Original prose approval/CMS controls, with labels recomputed from visible input.

These are authored synthetic controls, not collected user conversations or a
semantic model benchmark. No external examples, APIs or datasets are read.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import itertools
import json
from pathlib import Path
import random
import re

from .data import _hash, _write_dataset, validate_records


VERSION = "community-workflow-v3"
SPLITS = ("train",) * 6 + ("calibration", "validation", "test", "ood")
APPROVAL_OPTIONS = ["Permit this operation now", "Deny this operation", "Review before acting"]
CMS_OPTIONS = ["Apply the justified tags", "Leave the article untagged", "Request editorial review"]
APPROVAL_QUESTION = "Which decision follows the visible policy for the requested operation?"
APPROVAL_NOUL = "May the requested operation be performed now under the visible policy? Answer yes only when it is permitted, not when review is needed."
CMS_QUESTION = "What is the tagging status? Apply justified tags only when none is unresolved; leave untagged when all are ruled out; otherwise request editorial review."
SPLIT_POLICY = "ten_authored_rule_cards_per_task; six_train_one_calibration_one_validation_one_test_one_ood; all_scenarios_and_variants_grouped"

# (visible condition, affirmative reporting, explicit counterevidence).
# The parser recognizes these authored reporting forms; it never reads latent
# scenario flags, row metadata, targets, family names or construction indices.
APPROVAL_CARDS = [
    ("worker_restart", "restart the worker",
     ("a recoverable snapshot", "The snapshot restored successfully in a separate workspace.", "The snapshot is corrupt and cannot be restored."),
     ("a peer sign-off", "A second operator signed the change record.", "The second operator refused to sign the change record.")),
    ("credential_rotation", "rotate the service credential",
     ("a staged replacement credential", "The replacement credential is installed in the secret store.", "No replacement credential has been installed."),
     ("a compatible client", "The client accepted the replacement in a compatibility check.", "The client rejected the replacement in a compatibility check.")),
    ("fixture_removal", "remove the test fixtures",
     ("an expired retention period", "The fixtures have passed their required retention date.", "The required retention date is still in the future."),
     ("an isolated test workspace", "The workspace contains only disposable test records.", "The workspace also contains customer production records.")),
    ("billing_deployment", "deploy the billing revision",
     ("a passing regression run", "The full billing regression suite completed without a failure.", "The billing regression suite contains an unresolved failure."),
     ("a healthy canary", "The canary served its sample without elevated errors.", "The canary produced elevated errors on the sample.")),
    ("support_export", "export the support bundle",
     ("a verified requester", "The requester completed the required identity check.", "The requester failed the required identity check."),
     ("an owner-only export", "Every row in the bundle belongs to the requesting account.", "The bundle includes rows belonging to another account.")),
    ("reader_access", "grant reader access",
     ("an active team membership", "The person is listed as an active member of the project team.", "The person is not a member of the project team."),
     ("a read-only role", "The proposed role can read records but cannot write or delete them.", "The proposed role includes permission to delete records.")),
    ("pricing_publication", "publish the pricing notice",
     ("an agreed effective date", "The product owner signed off on the notice's effective date.", "The product owner rejected the notice's effective date."),
     ("a completed legal review", "Legal finished its review and accepted this wording.", "Legal rejected this wording during review.")),
    ("settlement_retry", "retry the settlement",
     ("a failed original attempt", "The original settlement failed before any funds moved.", "The original settlement already moved the funds successfully."),
     ("the original idempotency key", "The retry reuses the original settlement's idempotency key.", "The retry uses a newly generated idempotency key.")),
    ("project_archival", "archive the project",
     ("a project without active users", "The access audit found no active users on the project.", "The access audit found active users on the project."),
     ("a verified backup", "The backup was restored and checked against the source records.", "The backup could not be restored for verification.")),
    ("shipment_cancellation", "cancel the shipment",
     ("a parcel still in the warehouse", "The parcel is still on the warehouse shelf.", "The carrier has already collected the parcel."),
     ("the customer's confirmation", "The customer confirmed cancellation through the order portal.", "The customer explicitly rejected cancellation through the order portal.")),
]

# Each CMS rule card owns four distinct semantic conditions. Cards, not rows,
# determine splits. Mentioning a tag name is never evidence for the tag.
CMS_CARDS = [
    ("software_release", [
        ("API retirement", "an API retirement", "The legacy endpoint will be switched off in the next release.", "The legacy endpoint will remain supported in the next release."),
        ("Faster search", "a search speed improvement", "The new index cuts measured search time in half.", "The new index does not improve measured search time."),
        ("Accessibility", "a new accessibility feature", "This release adds keyboard navigation to every settings panel.", "This release adds no keyboard or screen-reader improvements."),
        ("Security fix", "a repaired vulnerability", "The patch closes the verified session-validation vulnerability.", "The session-validation vulnerability remains unfixed in this release.")]),
    ("city_notices", [
        ("Road closure", "a road closure", "Crews will close the bridge to road traffic during repairs.", "The bridge will stay open to road traffic during repairs."),
        ("Water outage", "a water-supply interruption", "Water supply will stop while crews replace the broken main.", "Water supply will continue throughout the repair."),
        ("Public hearing", "an open public hearing", "Residents can speak at the council's open hearing.", "The council is not holding a public hearing on this matter."),
        ("Transit detour", "a bus-route diversion", "Buses will use the riverside detour instead of the central stop.", "Buses will keep their normal route and central stop.")]),
    ("university_bulletin", [
        ("Grant call", "an open grant application", "Researchers may now submit applications for the seed grant.", "Applications for the seed grant are closed."),
        ("Scholarship", "an available student scholarship", "Students can apply for a tuition scholarship through the aid office.", "No tuition scholarship is available through this announcement."),
        ("Extended deadline", "an extended filing deadline", "The filing deadline has been moved two weeks later.", "The filing deadline has not been extended."),
        ("Campus closure", "a campus closure", "All campus buildings will close during the storm.", "Campus buildings will remain open during the storm.")]),
    ("retail_updates", [
        ("Product recall", "a product recall", "The manufacturer is recalling this batch and asking buyers to return it.", "The manufacturer has ruled out a recall for this batch."),
        ("Discount", "a current price reduction", "The shop has reduced the price for all orders placed this week.", "Prices for orders this week are unchanged."),
        ("Back in stock", "a replenished product", "The sold-out product is back on the shelf and ready to order.", "The product remains sold out and cannot be ordered."),
        ("Shipping delay", "a delivery delay", "Dispatch is running three days behind the advertised schedule.", "Dispatch is meeting the advertised schedule without delay.")]),
    ("arts_programme", [
        ("Tickets available", "an open ticket sale", "Tickets for the performance are now available to the public.", "Tickets for the performance are not yet on sale."),
        ("Cancelled event", "a cancelled performance", "The organizer has cancelled the performance and will issue refunds.", "The organizer confirmed that the performance will go ahead."),
        ("Venue change", "a relocated event", "The exhibition has moved from the hall to the riverside gallery.", "The exhibition will stay at its originally announced venue."),
        ("Live stream", "a live broadcast", "Viewers can watch the entire concert on a live stream.", "There will be no live stream of the concert.")]),
    ("library_services", [
        ("New branch", "a new library branch", "The library has opened an additional branch in the north district.", "The library is not opening an additional branch."),
        ("Longer hours", "extended opening hours", "The branch will remain open two hours later each evening.", "The branch's evening closing time will not change."),
        ("Digital archive", "a newly accessible digital collection", "Readers can now browse the digitized local newspaper collection online.", "The local newspaper collection is not available online."),
        ("Borrowing change", "a revised borrowing allowance", "Members may borrow twice as many books under the new allowance.", "The number of books members may borrow remains unchanged.")]),
    ("science_digest", [
        ("Dataset release", "a released research dataset", "The team has published the dataset for other researchers to download.", "The team has not released the dataset for download."),
        ("Correction", "a published research correction", "The journal issued a correction to the paper's reported measurements.", "The journal has not issued a correction to the paper."),
        ("Replication", "an independent replication result", "An independent laboratory repeated the experiment and reproduced the result.", "No independent laboratory has reproduced this result."),
        ("Equipment access", "shared instrument access", "Outside research teams may now book time on the new instrument.", "The instrument is restricted to the host laboratory's own team.")]),
    ("developer_docs", [
        ("Breaking change", "an incompatible interface change", "Existing clients must change their request format to use this endpoint.", "Existing clients can keep their request format without modification."),
        ("Migration guide", "an actionable migration guide", "The document provides the ordered commands needed to migrate old projects.", "The document does not provide steps for migrating old projects."),
        ("Version support", "an expanded supported-version range", "The SDK now supports the two newly released runtime versions.", "The SDK's supported runtime versions have not changed."),
        ("Runnable example", "a runnable worked example", "A complete example and its execution command are included in the guide.", "The guide includes only fragments that cannot run as an example.")]),
    ("workplace_policy", [
        ("Remote work", "a changed remote-work allowance", "The new policy permits three remote working days each week.", "The policy leaves the remote-work allowance unchanged."),
        ("Expenses", "a revised reimbursement rule", "The reimbursement policy now covers approved home-office equipment.", "Approved home-office equipment is still excluded from reimbursement."),
        ("Leave allowance", "additional paid leave", "Employees receive two additional paid leave days under this agreement.", "The agreement adds no paid leave days."),
        ("Training required", "mandatory staff training", "Every staff member must complete the new security course this month.", "The new security course is optional for staff.")]),
    ("environment_bulletin", [
        ("River cleanup", "a scheduled river cleanup", "Volunteers will remove litter from the riverbank on the announced date.", "The proposed riverbank cleanup has been called off."),
        ("Flood warning", "an active flood warning", "The regional office has issued a flood warning for the valley.", "The regional office confirms there is no flood warning for the valley."),
        ("Recycling change", "an expanded recycling service", "The collection service now accepts glass as well as paper.", "The collection service still accepts paper only, not glass."),
        ("Habitat restoration", "an approved habitat restoration", "The council approved planting native wetland species at the reserve.", "The council rejected the wetland restoration proposal.")]),
]

FACTS = {fact[0]: fact[1:] for _, _, first, second in APPROVAL_CARDS for fact in (first, second)}
FACTS.update({condition: (yes, no) for _, card in CMS_CARDS for _, condition, yes, no in card})
EXCEPTION = "The incident office signed an emergency authorization for this exact operation."
NO_EXCEPTION = "The incident office has issued no emergency authorization for this operation."
UNITS = ["workers", "clients", "fixture sets", "service instances", "support bundles",
         "workspaces", "regional notices", "settlements", "projects", "parcels"]
CMS_EVIDENCE_RULE = (
    "Use only current reporting, not a tag name or a quoted, archived, or hypothetical claim. "
    "A withdrawn announcement rules its claim out. Missing evidence or conflicting current claims are unresolved, not false. "
    "A tag needs affirmative current evidence. The paragraphs are independent; several tags may apply."
    " Paragraph order does not establish which conflicting claim is newer."
)
CMS_SECONDARY_CLAIMS = list(itertools.product(("yes", "no"), repeat=3)) + [
    ("unknown", "yes", "no"), ("conflict", "yes", "no"),
    ("yes", "unknown", "no"), ("yes", "conflict", "no"),
    ("yes", "no", "unknown"), ("yes", "no", "conflict"),
    ("unknown", "no", "yes"), ("conflict", "no", "yes"),
    ("no", "unknown", "yes"), ("no", "conflict", "yes"),
]


def truth_from_prose(text, condition):
    """Parse only the documented visible reporting forms, never latent flags."""
    yes, no = FACTS[condition]
    seen = set()
    for line in text.splitlines():
        if line.startswith(("Quoted comment:", "Archive:", "Hypothesis:")):
            continue
        if line.startswith("Withdrawn announcement:"):
            if yes in line:
                seen.add(False)
            continue
        if yes in line:
            seen.add(True)
        if no in line:
            seen.add(False)
    return next(iter(seen)) if len(seen) == 1 else None


def evidence_signature(text, condition):
    """Keep semantic evidence channels; discard cosmetic prefixes/line order."""
    yes, no = FACTS[condition]
    evidence = set()
    for line in text.splitlines():
        channel = next((name for name in ("Quoted comment", "Archive", "Hypothesis", "Withdrawn announcement")
                        if line.startswith(name + ":")), "current")
        for claim, sentence in (("affirmative", yes), ("negative", no)):
            if sentence in line:
                evidence.add((channel, claim))
    return sorted(evidence)


def semantic_context(state):
    """Normalize evidence, quantities and rules, without display names or labels."""
    if "editorial_policy" in state:
        cms_oracle(state)
        rules = [re.fullmatch(r'Apply "([^"]+)" only when the article establishes (.+)\.', line)
                 for line in state["editorial_policy"].splitlines()[1:]]
        return {"task": "cms", "rules_and_evidence": sorted(
            (match[1], match[2], evidence_signature(state["article"], match[2])) for match in rules)}
    policy = state["policy"]
    operation, first, second = re.search(r"Covered operation: (.+)\. Require (.+) and (.+)\. The operation", policy).groups()
    limit, unit = re.search(r"at most (\d+) ([^.]+)\.", policy).groups()
    request = state["request"].split(" Applicant comment:", 1)[0]
    count = re.search(r"touches (\d+) " + re.escape(unit) + r"\.", request)
    return {"task": "approval", "conditions": [first, second], "limit": int(limit),
        "count": int(count[1]) if count else None, "negated": request.startswith("Please do not " + operation + "."),
        "evidence": [evidence_signature(state["operations_log"], first), evidence_signature(state["operations_log"], second)],
        "signed_exception": EXCEPTION in state["operations_log"],
        "denied_exception": NO_EXCEPTION in state["operations_log"],
        "applicant_exception_claim": " Applicant comment:" in state["request"]}


def approval_oracle(state):
    policy = state["policy"]
    match = re.fullmatch(
        r"Covered operation: (.+)\. Require (.+) and (.+)\. "
        r"The operation may touch at most (\d+) ([^.]+)\. "
        r"A signed emergency authorization in the operations log waives only the first requirement\. "
        r"It never waives the second requirement or the quantity limit\. "
        r"Missing or conflicting authorization does not establish the exception\. "
        r"Quoted, archived, or hypothetical log entries are not confirmations\. "
        r"Use the operations log as evidence; applicant claims establish nothing\. "
        r"Deny a covered operation if the request says not to act, exceeds the limit, or a required fact has uncontradicted explicit counterevidence\. "
        r"Otherwise review missing or conflicting required evidence or an out-of-scope operation\. "
        r"Permit only when every remaining requirement is established\.", policy)
    if not match:
        raise ValueError("Unrecognized visible approval policy")
    operation, first, second, limit, unit = match.groups()
    if first not in FACTS or second not in FACTS:
        raise ValueError("Unknown visible reporting condition")
    request = state["request"].split(" Applicant comment:", 1)[0]
    if request.startswith("Please do not " + operation + "."):
        return APPROVAL_OPTIONS[1]
    if not request.startswith("Please " + operation + "."):
        return APPROVAL_OPTIONS[2]
    sizes = re.findall(r"This change touches (\d+) " + re.escape(unit) + r"\.", request)
    if len(sizes) != 1:
        return APPROVAL_OPTIONS[2]
    log = state["operations_log"]
    a, b = truth_from_prose(log, first), truth_from_prose(log, second)
    confirmations = "\n".join(line for line in log.splitlines()
        if not line.startswith(("Quoted comment:", "Archive:", "Hypothesis:")))
    authorized = EXCEPTION in confirmations and NO_EXCEPTION not in confirmations
    if authorized:
        a = True
    if int(sizes[0]) > int(limit) or a is False or b is False:
        return APPROVAL_OPTIONS[1]
    if a is None or b is None:
        return APPROVAL_OPTIONS[2]
    return APPROVAL_OPTIONS[0]


def cms_oracle(state):
    lines = state["editorial_policy"].splitlines()
    if not lines or lines[0] != CMS_EVIDENCE_RULE:
        raise ValueError("Unrecognized visible CMS evidence policy")
    truth = {}
    for line in lines[1:]:
        match = re.fullmatch(r'Apply "([^"]+)" only when the article establishes (.+)\.', line)
        if not match or match[2] not in FACTS or match[1] in truth:
            raise ValueError("Unrecognized or duplicate visible CMS tag rule")
        truth[match[1]] = truth_from_prose(state["article"], match[2])
    if len(truth) != 4:
        raise ValueError("A CMS policy must define four independent candidate tags")
    verdict = CMS_OPTIONS[2] if any(v is None for v in truth.values()) else CMS_OPTIONS[0] if any(truth.values()) else CMS_OPTIONS[1]
    return verdict, truth


def expected_target(row):
    """Independent visible-input label reconstruction for generated records."""
    if "policy" in row["state"]:
        answer = approval_oracle(row["state"])
        if row["kind"] == "noul" and row["question"] == APPROVAL_NOUL:
            answer = "yes" if answer == APPROVAL_OPTIONS[0] else "no"
        elif row["kind"] != "choice" or row["question"] != APPROVAL_QUESTION:
            raise ValueError("Unrecognized approval question")
    else:
        answer, truths = cms_oracle(row["state"])
        if row["kind"] == "noul":
            match = re.fullmatch(r'Is the tag "([^"]+)" justified by the article under the editorial policy\? Answer yes only for affirmative support; unresolved evidence is not sufficient\.', row["question"])
            if not match or match[1] not in truths:
                raise ValueError("Unrecognized CMS question")
            answer = "yes" if truths[match[1]] is True else "no"
        elif row["kind"] != "choice" or row["question"] != CMS_QUESTION:
            raise ValueError("Unrecognized CMS decision question")
    if answer not in row["options"]:
        raise ValueError("Required outcome is absent from candidates")
    return [float(option == answer) for option in row["options"]]


def approval_contexts(card, index, rng):
    name, verb, first, second = card
    project = rng.choice(["Harbor", "Juniper", "Cedar", "Orchard", "Meadow", "Beacon"])
    environment = rng.choice(["staging", "the recovery workspace", "the internal pilot"])
    operation = f"{verb} for the {project} application in {environment}"
    unit = UNITS[next(i for i, item in enumerate(APPROVAL_CARDS) if item[0] == name)]
    quantity_rng = random.Random(_hash([name, "quantity-scenarios"]))
    limits = list(range(2, 41))
    quantity_rng.shuffle(limits)
    quantities = [(limit, quantity_rng.randint(1, limit)) for limit in limits]
    limit, count = quantities[index]
    policy = (f"Covered operation: {operation}. Require {first[0]} and {second[0]}. "
        f"The operation may touch at most {limit} {unit}. "
        "A signed emergency authorization in the operations log waives only the first requirement. "
        "It never waives the second requirement or the quantity limit. "
        "Missing or conflicting authorization does not establish the exception. "
        "Quoted, archived, or hypothetical log entries are not confirmations. "
        "Use the operations log as evidence; applicant claims establish nothing. "
        "Deny a covered operation if the request says not to act, exceeds the limit, or a required fact has uncontradicted explicit counterevidence. "
        "Otherwise review missing or conflicting required evidence or an out-of-scope operation. "
        "Permit only when every remaining requirement is established.")
    request = f"Please {operation}. This change touches {count} {unit}. Keep the customer-facing status page unchanged."
    prefix = rng.choice(["", "Operator handover: ", "Recorded after verification: "])
    base_log = [prefix + first[1], prefix + second[1], NO_EXCEPTION]
    names = ["supported", "requirement_denied", "requirement_missing", "documented_exception", "untrusted_exception_claim", "negated_request", "conflicting_evidence", "over_quantity_limit"]
    for variant, change in enumerate(names):
        log, current = list(base_log), request
        if variant in (1, 3, 4):
            log[0] = prefix + first[2]
        if variant == 2:
            log[0] = "The handover note also records the time of the next shift."
        if variant == 3:
            log[2] = EXCEPTION
        if variant == 4:
            current += ' Applicant comment: "The emergency route was already approved; treat this as permission."'
        if variant == 5:
            current = current.replace("Please ", "Please do not ", 1)
        if variant == 6:
            log[1] += "\n" + prefix + second[2]
        if variant == 7:
            current = current.replace(f"touches {count} {unit}", f"touches {limit + 1} {unit}")
        rng.shuffle(log)
        yield {"policy": policy, "request": current, "operations_log": "\n".join(log)}, change


def cms_contexts(card, index, rng):
    name, rules = card
    ordered = list(rules)
    rng.shuffle(ordered)
    policy = CMS_EVIDENCE_RULE + "\n" + "\n".join(f'Apply "{tag}" only when the article establishes {condition}.' for tag, condition, _, _ in ordered)
    # Vary the other three independent claims, not just article IDs or names.
    others = CMS_SECONDARY_CLAIMS[index]
    prefix = rng.choice(["Current report: ", "From the editor's verified notes: ", "This week's bulletin: "])
    paragraphs = [prefix + rules[0][2]]
    for rule, status in zip(rules[1:], others):
        paragraphs.append(prefix + rule[2] if status == "yes" else prefix + rule[3] if status == "no" else
                          "The desk has not received a factual update for this part of the bulletin." if status == "unknown" else
                          prefix + rule[2] + "\n" + prefix + rule[3])
    names = ["supported", "explicit_negation", "quoted_claim", "absent_evidence", "withdrawn_exception", "conflicting_claims"]
    for variant, change in enumerate(names):
        current = list(paragraphs)
        if variant == 1:
            current[0] = prefix + rules[0][3]
        elif variant == 2:
            current[0] = 'Quoted comment: "' + rules[0][2] + '" The editor has not verified this claim.'
        elif variant == 3:
            current[0] = "The submission ends with a note about copy-editing; it adds no factual announcement."
        elif variant == 4:
            current[0] = "Withdrawn announcement: " + rules[0][2] + " This announcement is no longer in effect."
        elif variant == 5:
            current[0] += "\n" + prefix + rules[0][3]
        rng.shuffle(current)
        # Tag-name mentions occur in every variant, including explicit negatives.
        article = (f"Desk note for the {name.replace('_', ' ')} edition.\n"
                   "Possible index terms discussed by editors: " + ", ".join(rule[0] for rule in rules) + ".\n\n" + "\n\n".join(current))
        yield {"editorial_policy": policy, "article": article}, change


def generate(groups_per_family=18, seed=20260921):
    if type(groups_per_family) is not int or not 1 <= groups_per_family <= len(CMS_SECONDARY_CLAIMS):
        raise ValueError("groups_per_family must be an integer between 1 and 18")
    for domain, cards, make_contexts in (("approval", APPROVAL_CARDS, approval_contexts), ("cms", CMS_CARDS, cms_contexts)):
        for family_index, card in enumerate(cards):
            family = domain + "/" + card[0]
            for index in range(groups_per_family):
                group = f"{VERSION}/{seed}/{family}/{index}"
                rng = random.Random(_hash([group, "context"]))
                for variant, (state, change) in enumerate(make_contexts(card, index, rng)):
                    views = [("choice", APPROVAL_QUESTION if domain == "approval" else CMS_QUESTION)]
                    if domain == "approval":
                        views.append(("noul", APPROVAL_NOUL))
                    else:
                        views.extend(("noul", f'Is the tag "{tag}" justified by the article under the editorial policy? Answer yes only for affirmative support; unresolved evidence is not sufficient.') for tag, *_ in card[1])
                    for view, (kind, question) in enumerate(views):
                        options = list(APPROVAL_OPTIONS if domain == "approval" else CMS_OPTIONS) if kind == "choice" else ["no", "yes"]
                        if kind == "choice":
                            random.Random(_hash([group, variant, "options"])).shuffle(options)
                        row = {"id": f"{group}/{variant}/{view}", "group_id": group, "split": SPLITS[family_index],
                            "source": VERSION + "/" + domain, "state": state, "question": question, "kind": kind,
                            "options": options, "target": [], "metadata": {"family": "policy" if domain == "approval" else "evidence",
                                "domain": domain, "language": "en", "scenario_family": family, "template_id": VERSION + "/" + family,
                                "source_instance_id": group, "counterfactual": change, "variant": variant,
                                "target_basis": "visible_prose_policy_and_authored_reporting_contract",
                                "provenance": {"type": "synthetic", "generator_version": VERSION, "seed": seed,
                                    "group_index": index, "variant": variant, "license": "CC0-1.0", "split_policy": SPLIT_POLICY,
                                    "source_examples_imported": False}}}
                        row["target"] = expected_target(row)
                        yield row


def audit_records(rows):
    summary = validate_records(rows)
    families, groups, visible, context_groups = {}, {}, {}, defaultdict(set)
    outcomes, word_counts = Counter(), []
    answers_by_group = defaultdict(lambda: defaultdict(set))
    semantic_groups, semantic_contexts, cms_truths = defaultdict(set), defaultdict(set), set()
    semantic_membership = {}
    for row in rows:
        input_only = {key: row[key] for key in ("state", "question", "kind", "options")}
        if row["target"] != expected_target(input_only):
            raise ValueError("Target differs from visible-only oracle")
        state = row["state"]
        if set(state) not in ({"policy", "request", "operations_log"}, {"editorial_policy", "article"}) or not all(isinstance(value, str) for value in state.values()):
            raise ValueError("State must contain only policy/request/document prose")
        for mapping, key in ((families, row["metadata"]["scenario_family"]), (groups, row["group_id"]), (visible, _hash(input_only))):
            if key in mapping and mapping[key] != row["split"]:
                raise ValueError("Rule family, scenario or visible input crosses splits")
            mapping[key] = row["split"]
        context_groups[_hash(state)].add(row["group_id"])
        contract = (row["question"], row["kind"], tuple(sorted(row["options"])))
        answers_by_group[row["group_id"]][contract].add(row["options"][row["target"].index(1.)])
        if row["kind"] == "choice":
            domain = row["metadata"]["domain"]
            signature = _hash(semantic_context(state))
            semantic_contexts[domain].add(signature)
            if signature in semantic_membership and semantic_membership[signature] != row["group_id"]:
                raise ValueError("Semantic context repeats across source scenario groups")
            semantic_membership[signature] = row["group_id"]
            if row["metadata"]["variant"] == 0:
                semantic_groups[domain].add(signature)
            if domain == "cms":
                cms_truths.add(_hash(cms_oracle(state)[1]))
            label = row["options"][row["target"].index(1.)]
            outcomes[row["metadata"]["domain"] + "/" + label] += 1
            word_counts.append(len(" ".join(state.values()).split()))
    # A constant question/candidate contract receives different targets when the
    # visible prose changes. IDs, metadata and target fields were never consulted.
    for contracts in answers_by_group.values():
        if not any(len(answers) >= 2 for answers in contracts.values()):
            raise ValueError("Counterfactual group does not change a visible decision")
    duplicate_groups = sum(len(value) > 1 for value in context_groups.values())
    if duplicate_groups:
        raise ValueError("A context was duplicated across source scenario groups")
    return {"summary": summary, "scenario_family_count": len(families), "source_scenario_count": len(groups),
        "unique_contexts": len(context_groups), "outcomes": dict(outcomes),
        "semantic_scenarios_by_domain": {key: len(value) for key, value in semantic_groups.items()},
        "semantic_contexts_by_domain": {key: len(value) for key, value in semantic_contexts.items()},
        "cms_authoritative_truth_states": len(cms_truths),
        "semantic_normalization": "Tag/rule definitions and affirmative/negative evidence channels, ignoring prose wrapper and paragraph order; approval also retains distinct quantity pairs. Unknown and conflicting evidence remain distinct contexts even when both require review.",
        "domain_counts": dict(Counter(row["metadata"]["domain"] for row in rows)),
        "noul_outcomes": dict(Counter(row["metadata"]["domain"] + "/" + row["options"][row["target"].index(1.)]
                                      for row in rows if row["kind"] == "noul")),
        "context_words": {"min": min(word_counts), "max": max(word_counts), "median": sorted(word_counts)[len(word_counts)//2]},
        "checks": {"all_targets_visible_input_only": True, "all_states_prose_only": True,
            "rule_family_and_scenario_disjoint": True, "visible_input_disjoint": True,
            "no_duplicate_contexts_across_scenario_groups": True, "no_cosmetic_duplicate_scenarios": True,
            "normalized_semantic_splits_disjoint": True, "counterfactuals_change_decisions": True}}


def build_dataset(output_dir, groups_per_family=18, seed=20260921):
    output = Path(output_dir)
    if output.is_symlink() or output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("Choose a new empty output directory")
    rows = list(generate(groups_per_family, seed))
    audit = audit_records(rows)
    configuration = {"type": "synthetic", "version": VERSION, "seed": seed, "groups_per_family": groups_per_family,
        "license": "CC0-1.0", "split_policy": SPLIT_POLICY,
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "external_examples_imported": False, "benchmark_inputs_read": False, "paid_calls": 0,
        "limitations": ["Original English synthetic prose controls, not real user logs or independently collected human labels.",
            "Twenty authored rule cards share a finite reporting grammar; held-out cards do not prove unrestricted language transfer.",
            "Related task views/counterfactuals are correlated and must not be counted as independent documents.",
            "The visible oracle validates the authored grammar, not arbitrary prose semantics.",
            "No training, API evaluation or measured improvement is performed by this builder."]}
    manifest = _write_dataset(rows, output, configuration)
    manifest.update(audit)
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--groups-per-family", type=int, default=18)
    parser.add_argument("--seed", type=int, default=20260921)
    args = parser.parse_args()
    manifest = build_dataset(args.output_dir, args.groups_per_family, args.seed)
    print(json.dumps({key: manifest[key] for key in ("summary", "scenario_family_count", "source_scenario_count", "unique_contexts", "domain_counts")}, indent=2))


if __name__ == "__main__":
    main()
