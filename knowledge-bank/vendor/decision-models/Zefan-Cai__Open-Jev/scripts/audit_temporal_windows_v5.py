"""Independent epoch-second audit; never imports the time-control generator."""
import argparse
import calendar
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

from jev.data import SPLITS, validate_records


TIMESTAMP = re.compile(r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})([+-])(\d{2}):(\d{2})\Z")
PROPOSAL = re.compile(r"Does the supplied policy establish the outcome '(accept|reject|review)'\? Determine the route from the request and delivery timestamps\.\Z")
POLICIES = {
    "Accept from delivery through delivery plus the stated hours, including both endpoints. Reject outside this window. An approved exception overrides either outcome with review. Compare absolute instants using the explicit fixed UTC offsets.",
    "The permitted interval starts at delivery and ends the stated number of hours later; both limits are included. Outside it, reject. If an exception is approved, use review instead. Displayed local dates and clocks must be interpreted with their fixed UTC offsets.",
}


def epoch_seconds(text):
    """Validate calendar fields, then subtract the explicit offset in integer seconds."""
    match = TIMESTAMP.fullmatch(text)
    if match is None:
        raise ValueError("An explicit fixed UTC offset and whole seconds are required")
    year, month, day, hour, minute, second = map(int, match.groups()[:6])
    offset_hour, offset_minute = map(int, match.groups()[7:])
    if offset_hour > 23 or offset_minute > 59:
        raise ValueError("Invalid UTC offset")
    local = datetime(year, month, day, hour, minute, second)
    offset = (offset_hour * 60 + offset_minute) * (1 if match[7] == "+" else -1)
    return calendar.timegm(local.timetuple()) - offset * 60


def expected_outcome(state):
    if state["policy"] not in POLICIES:
        raise ValueError("Unsupported authored policy")
    hours = state["return_window_hours"]
    if type(hours) is not int or hours <= 0 or type(state["exception_approved"]) is not bool:
        raise ValueError("Invalid window or exception flag")
    elapsed = epoch_seconds(state["request_received_at"]) - epoch_seconds(state["delivered_at"])
    if state["exception_approved"]:
        return "review"
    return "accept" if 0 <= elapsed <= hours * 3600 else "reject"


def audit_rows(rows):
    schema = validate_records(rows)
    groups = defaultdict(dict)
    coverage = {split: Counter() for split in SPLITS}
    offsets = {split: set() for split in SPLITS}
    noul_truths = {split: Counter() for split in SPLITS}
    case_groups, input_splits = {}, {}
    for row in rows:
        state, split = row["state"], row["split"]
        answer = expected_outcome(state)
        if row["kind"] == "noul":
            proposal = PROPOSAL.fullmatch(row["question"])
            if proposal is None or proposal[1] != row["metadata"]["proposed_outcome"]:
                raise ValueError("Visible Noul proposal disagrees with metadata")
            answer = "yes" if answer == proposal[1] else "no"
            noul_truths[split][answer] += 1
        elif row["kind"] != "choice" or set(row["options"]) != {"accept", "reject", "review"}:
            raise ValueError("Unsupported decision type or options")
        expected = [float(option == answer) for option in row["options"]]
        if row["target"] != expected:
            raise ValueError("Independent epoch oracle disagrees with target: " + row["id"])
        variant = row["metadata"]["provenance"]["variant"]
        if variant in groups[row["group_id"]]:
            raise ValueError("Duplicate counterfactual variant")
        groups[row["group_id"]][variant] = row
        start, request = (epoch_seconds(state[k]) for k in ("delivered_at", "request_received_at"))
        case_facts = (start, state["return_window_hours"])
        if case_facts in case_groups and case_groups[case_facts] != row["group_id"]:
            raise ValueError("Case-ID-independent temporal facts repeat across groups")
        case_groups[case_facts] = row["group_id"]
        visible = {"state": {k: v for k, v in state.items() if k != "case"},
                   "question": " ".join(row["question"].split()), "kind": row["kind"],
                   "options": sorted(row["options"])}
        fingerprint = json.dumps(visible, sort_keys=True, separators=(",", ":"))
        if fingerprint in input_splits and input_splits[fingerprint] != split:
            raise ValueError("Case-ID-independent model input repeats across splits")
        input_splits[fingerprint] = split
        deadline = start + state["return_window_hours"] * 3600
        relationship = "before_delivery" if request < start else "at_delivery" if request == start else "inside_window" if request < deadline else "at_deadline" if request == deadline else "after_deadline"
        coverage[split][relationship] += 1
        coverage[split]["exception_overrides"] += int(state["exception_approved"])
        offset_pair = tuple(state[k][-6:] for k in ("delivered_at", "request_received_at"))
        offsets[split].update(offset_pair)
        coverage[split]["different_display_offsets"] += int(offset_pair[0] != offset_pair[1])
        a, b = (datetime.fromtimestamp(t, timezone.utc) for t in (start, request))
        coverage[split]["cross_utc_date"] += int(a.date() != b.date())
        coverage[split]["cross_utc_month"] += int((a.year, a.month) != (b.year, b.month))
        coverage[split]["cross_utc_year"] += int(a.year != b.year)
        coverage[split]["touches_utc_leap_day"] += int((a.month, a.day) == (2, 29) or (b.month, b.day) == (2, 29))
    for variants in groups.values():
        if set(variants) != {0, 1, 2, 3} or Counter(r["kind"] for r in variants.values()) != {"choice": 3, "noul": 1}:
            raise ValueError("Every group requires four complete variants: three Choice, one Noul")
        first = variants[0]["state"]
        if any(any(r["state"][k] != first[k] for k in ("case", "delivered_at", "return_window_hours", "policy")) for r in variants.values()):
            raise ValueError("Counterfactuals disagree on shared case facts")
        start = epoch_seconds(first["delivered_at"])
        deadline = start + first["return_window_hours"] * 3600
        edge = epoch_seconds(variants[1]["state"]["request_received_at"])
        requests = [epoch_seconds(variants[i]["state"]["request_received_at"]) for i in range(4)]
        if edge not in (start, deadline) or requests != [edge - 1, edge, edge + 1, deadline + 1]:
            raise ValueError("Group does not straddle one inclusive boundary and an exception")
        if [variants[i]["state"]["exception_approved"] for i in range(4)] != [False, False, False, True]:
            raise ValueError("Counterfactual exception pattern changed")
    required = {"before_delivery", "at_delivery", "inside_window", "at_deadline", "after_deadline",
                "exception_overrides", "different_display_offsets", "cross_utc_date", "cross_utc_month", "cross_utc_year"}
    for split in SPLITS:
        if any(coverage[split][name] == 0 for name in required) or len(offsets[split]) < 3:
            raise ValueError("Missing representative boundary/offset coverage in " + split)
        if not noul_truths[split]["yes"] or noul_truths[split]["yes"] != noul_truths[split]["no"]:
            raise ValueError("Noul truth balance changed in " + split)
    if not coverage["ood"]["touches_utc_leap_day"]:
        raise ValueError("OOD leap-day coverage is missing")
    return {"schema": schema, "oracle_checked": len(rows), "complete_four_row_groups": len(groups),
            "group_case_input_split_disjointness": "passed", "coverage": {k: dict(v) for k, v in coverage.items()},
            "case_id_independent_group_and_input_disjointness": "passed",
            "distinct_temporal_case_facts": len(case_groups),
            "display_offsets": {k: sorted(v) for k, v in offsets.items()},
            "noul_truths": {k: dict(v) for k, v in noul_truths.items()},
            "scope": "Independent integer-second validation of authored synthetic window rules; no model evaluation or arbitrary-prose validation"}


def audit_directory(directory):
    directory = Path(directory)
    manifest_raw = (directory / "manifest.json").read_bytes()
    manifest = json.loads(manifest_raw)
    if set(manifest["files_sha256"]) != {split + ".jsonl" for split in SPLITS}:
        raise ValueError("Manifest must freeze all five split files")
    rows = []
    for name, expected in manifest["files_sha256"].items():
        raw = (directory / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError("Frozen split checksum changed: " + name)
        selected = [json.loads(line) for line in raw.splitlines()]
        if any(row["split"] != Path(name).stem for row in selected):
            raise ValueError("Record is in the wrong frozen split file")
        rows.extend(selected)
    result = audit_rows(rows)
    if result["schema"] != manifest["summary"]:
        raise ValueError("Manifest summary disagrees with records")
    return {"status": "validated_no_model_run", "manifest_sha256": hashlib.sha256(manifest_raw).hexdigest(),
            "files_sha256": manifest["files_sha256"], "generator_sha256": manifest["generator_sha256"],
            "validator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), **result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit_directory(args.dataset)
    with args.output.open("x") as handle:
        handle.write(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in ("status", "oracle_checked", "complete_four_row_groups")}, indent=2))


if __name__ == "__main__":
    main()
