"""Audit generated SQL data without importing its generator or business oracle."""
import argparse
from collections import Counter, defaultdict
import copy
from datetime import date
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def visible_events(state):
    events = copy.deepcopy(state["tables"]["events"])
    accounts = {a["account_ref"]: a["customer_id"] for a in state["tables"].get("accounts", [])}
    for event in events:
        if "account_ref" in event:
            event["customer_id"] = accounts.get(event.pop("account_ref"))
    return events


def rounded(value, places):
    # A different arithmetic implementation of the stated away-from-zero ties.
    factor = 10 ** places
    return math.copysign(math.floor(abs(value) * factor + .5) / factor, value)


def independently_requested_value(state):
    """Dispatch only on the visible metric definition; never inspect metadata."""
    request, tables, parameters = state["business_request"], state["tables"], state["parameters"]
    events = visible_events(state)
    amounts = [event["amount"] for event in events]
    if request.startswith("Return total invoiced minor units:"):
        return sum(event["quantity"] * event["amount"] for event in events)
    if request.startswith("Return the unweighted sum of listed unit prices"):
        return sum(amounts)
    if request.startswith("Count distinct non-NULL customer IDs"):
        return len(set(event["customer_id"] for event in events) - {None})
    if request.startswith("Count all event rows,"):
        return len(events)
    if request.startswith("Return the average amount over known amounts only;"):
        values = [value for value in amounts if value is not None]
        return rounded(sum(values) / len(values), 6)
    if request.startswith("Return the average amount over every event,"):
        return rounded(sum(value or 0 for value in amounts) / len(events), 6)
    if request.startswith("Sum amounts from start_day inclusive to end_day"):
        include_end = "end_day inclusive." in request
        selected = [event for event in events if event["activity_day"] >= parameters["start_day"]
                    and (event["activity_day"] <= parameters["end_day"] if include_end
                         else event["activity_day"] < parameters["end_day"])]
        return sum(event["amount"] for event in selected)
    if request.startswith("Return the total amount in"):
        converted = sum(event["amount"] * {"cent": 1, "dollar": 100}[event["unit"]] for event in events)
        return rounded(converted / 100, 2) if "in dollars," in request else converted
    if request.startswith("Return gross event amounts minus settled refunds only."):
        total = sum(amounts)
        for refund in tables["refunds"]:
            if refund["refund_status"] == "settled":
                total -= refund["refund_amount"]
        return total
    if request.startswith("Return gross event amounts before refunds."):
        return sum(amounts)
    if request.startswith("Sum the amount of each event having at least one target_tag"):
        matches = {tag["event_id"] for tag in tables["tags"] if tag["tag"] == parameters["target_tag"]}
        return sum(event["amount"] for event in events if event["event_id"] in matches)
    if request.startswith("Sum event amounts once for every matching target_tag"):
        amount_by_id = {event["event_id"]: event["amount"] for event in events}
        return sum(amount_by_id[tag["event_id"]] for tag in tables["tags"] if tag["tag"] == parameters["target_tag"])
    if request.startswith("Count directory customers with"):
        found = sum(any(event["customer_id"] == customer["customer_id"] for event in events)
                    for customer in tables["directory"])
        return len(tables["directory"]) - found if "with no matching event." in request else found
    if request.startswith("Return total successes divided by total trials"):
        return rounded(sum(event["successes"] for event in events) / sum(event["trials"] for event in events), 6)
    if request.startswith("Return the unweighted mean of each event's successes/trials rate"):
        rates = [event["successes"] / event["trials"] for event in events]
        return rounded(sum(rates) / len(rates), 6)
    if request.startswith("Count customers whose sum of event amounts"):
        customers = {event["customer_id"] for event in events}
        return sum(sum(event["amount"] for event in events if event["customer_id"] == customer) >= parameters["threshold"]
                   for customer in customers)
    if request.startswith("Count customers having at least one individual event amount"):
        return len({event["customer_id"] for event in events if event["amount"] >= parameters["threshold"]})
    if request.startswith("Sum the latest amount snapshot") or request.startswith("Sum the earliest amount snapshot"):
        ordered = sorted(events, key=lambda event: (event["activity_day"], event["event_id"]),
                         reverse=request.startswith("Sum the latest"))
        chosen = {}
        for event in ordered:
            chosen.setdefault(event["customer_id"], event["amount"])
        return sum(chosen.values())
    if request.startswith("Return the average total event amount"):
        totals = []
        for customer in tables["directory"]:
            matched = [event for event in events if event["customer_id"] == customer["customer_id"]]
            if matched or "including customers with no events as zero" in request:
                totals.append(sum(event["amount"] for event in matched))
        return rounded(sum(totals) / len(totals), 6)
    raise ValueError("Unrecognized visible business request")


def normalized_database(state):
    """Ignore row order, key names/values and the absolute origin of dates."""
    events = sorted(visible_events(state), key=lambda event: event["event_id"])
    event_keys = {event["event_id"]: i for i, event in enumerate(events)}
    customer_keys = {}
    for event in events:
        if event["customer_id"] is not None:
            customer_keys.setdefault(event["customer_id"], len(customer_keys))
    for customer in sorted(state["tables"].get("directory", []), key=lambda item: item["customer_id"]):
        customer_keys.setdefault(customer["customer_id"], len(customer_keys))
    days = [event["activity_day"] if isinstance(event["activity_day"], int) else
            (date.fromisoformat(event["activity_day"]) - date(2024, 1, 1)).days for event in events]
    for event, day in zip(events, days):
        event["event_id"] = event_keys[event["event_id"]]
        event["customer_id"] = customer_keys.get(event["customer_id"])
        event["activity_day"] = day - min(days)
    result = {"events": events}
    for table, records in state["tables"].items():
        if table in ("events", "accounts"):
            continue
        copied = []
        for record in records:
            record = {key: value for key, value in record.items() if key not in ("refund_id", "tag_id")}
            if "event_id" in record:
                record["event_id"] = event_keys[record["event_id"]]
            if "customer_id" in record:
                record["customer_id"] = customer_keys[record["customer_id"]]
            copied.append(record)
        result[table] = sorted(copied, key=lambda record: json.dumps(record, sort_keys=True))
    return digest(result)


def audit(directory):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    raw_databases, normalized, families = defaultdict(set), defaultdict(set), defaultdict(set)
    counts, fanout, nulls, matched_counts = Counter(), Counter(), 0, Counter()
    contexts, groups, template_sets = set(), defaultdict(list), set()
    queries = 0
    for name, expected_hash in manifest["files_sha256"].items():
        path = directory / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
            raise ValueError("Dataset file checksum mismatch")
        for line in path.open():
            row = json.loads(line)
            state = row["state"]
            expected = [[independently_requested_value(state)]]
            connection = sqlite3.connect(":memory:")
            connection.executescript("\n".join(state["schema"]))
            for table, records in state["tables"].items():
                for record in records:
                    names = list(record)
                    connection.execute(f"INSERT INTO {table} ({','.join(names)}) VALUES ({','.join('?' for _ in names)})", list(record.values()))
            connection.commit()
            connection.execute("PRAGMA query_only = ON")
            results = []
            for query in row["options"]:
                results.append([list(result) for result in connection.execute(query)])
                queries += 1
            connection.close()
            matches = [result == expected for result in results]
            nulls += sum(result == [[None]] for result in results)
            if not any(matches) or all(matches):
                raise ValueError("No meaningful SQL choice")
            correct = [int(match) / sum(matches) for match in matches]
            if correct != row["target"] or expected != row["metadata"]["reference_result"] or results != row["metadata"]["candidate_results"]:
                raise ValueError("Independent SQL/meaning replay mismatch")
            normalized[normalized_database(state)].add(row["split"])
            raw_databases[digest({"schema": state["schema"], "tables": state["tables"]})].add(row["split"])
            families[row["metadata"]["structural_family"]].add(row["split"])
            fingerprint = digest({"state": state, "options": sorted(row["options"])})
            if fingerprint in contexts:
                raise ValueError("Duplicate decision")
            contexts.add(fingerprint)
            groups[row["group_id"]].append(row)
            template_sets.add(digest(sorted(re.sub(r"'[^']*'|\b\d+(?:\.\d+)?\b", "?", query) for query in row["options"])))
            counts[row["split"]] += 1
            matched_counts[sum(matches)] += 1
            fanout[len(row["options"])] += 1
    for registry in (raw_databases, families):
        if any(len(splits) != 1 for splits in registry.values()):
            raise ValueError("Structural family or database crosses splits")
    for pair in groups.values():
        if len(pair) != 2 or pair[0]["split"] != pair[1]["split"] or pair[0]["options"] != pair[1]["options"]:
            raise ValueError("Malformed counterfactual pair")
        if [key for key in pair[0]["state"] if pair[0]["state"][key] != pair[1]["state"][key]] != ["business_request"]:
            raise ValueError("Counterfactual changes more than the request")
        if independently_requested_value(pair[0]["state"]) == independently_requested_value(pair[1]["state"]):
            raise ValueError("Counterfactual fails to change the answer")
    return {"auditor_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "generator_imported": False, "metadata_used_by_business_interpreter": False,
            "rows_replayed": sum(counts.values()), "sqlite_queries_replayed": queries,
            "split_counts": dict(counts), "unique_visible_databases": len(raw_databases),
            "identifier_and_date_origin_normalized_databases": len(normalized),
            "normalized_databases_crossing_splits": sum(len(splits) > 1 for splits in normalized.values()),
            "unique_contexts": len(contexts), "structural_operator_layout_families": len(families),
            "literal_normalized_sql_template_sets": len(template_sets), "counterfactual_edges": len(groups),
            "candidate_counts": dict(fanout), "equivalent_candidate_counts": dict(matched_counts),
            "null_candidate_results": nulls, "sql_errors": 0, "label_disagreements": 0,
            "file_checksums_verified": manifest["files_sha256"],
            "checks": {"independent_visible_business_interpretation": True, "independent_sqlite_execution": True,
                       "equivalent_answers_receive_equal_probability": True, "wrong_choices_differ_on_visible_data": True,
                       "single_request_counterfactual_changes_answer": True, "raw_database_and_layout_family_disjoint": True}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.data)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
