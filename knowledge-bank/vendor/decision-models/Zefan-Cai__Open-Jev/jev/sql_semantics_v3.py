"""Original SQLite business-semantic choices with independently computed answers.

No external datasets, SQL examples or benchmark questions are read.  SQLite is
used only after a Python business interpreter computes the requested result.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import copy
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
import math
from pathlib import Path
import random
import re
import sqlite3

from .data import _hash, _write_dataset, validate_records

VERSION = "sql-semantics-v3"
INSPIRATION = "https://github.com/ryan-sunny/dbt-assay/tree/ebf8812c9aeb19747f7168a0e08d3d224e170b12"
SPLIT_POLICY = "semantic_operator_x_layout_family_disjoint_4train_1cal_1val_1test_1ood"
PROFILE_SPLITS = ("train", "train", "train", "calibration", "train", "validation", "test", "ood")
QUESTION = ("Which SQL candidate returns the requested result on exactly the complete visible database? "
            "Distribute probability uniformly over all candidates with an equivalent result. "
            "Do not judge behavior on unseen rows. All candidates are read-only SQLite queries.")
REQUESTS = {
    "extended_amount": (
        "Return total invoiced minor units: sum unit price times quantity over all events.",
        "Return the unweighted sum of listed unit prices, counting each event once regardless of quantity."),
    "distinct_customers": (
        "Count distinct non-NULL customer IDs that occur in events.",
        "Count all event rows, including rows with a NULL customer ID."),
    "null_average": (
        "Return the average amount over known amounts only; exclude NULL amounts from the denominator. Round to 6 decimal places, halfway cases away from zero.",
        "Return the average amount over every event, treating NULL amounts as zero. Round to 6 decimal places, halfway cases away from zero."),
    "time_window": (
        "Sum amounts from start_day inclusive to end_day exclusive. Return zero for an empty window.",
        "Sum amounts from start_day inclusive to end_day inclusive. Return zero for an empty window."),
    "unit_conversion": (
        "Return the total amount in cents. Each unit is either cent or dollar; one dollar is 100 cents.",
        "Return the total amount in dollars, rounded to 2 decimal places, halfway cases away from zero. Each unit is either cent or dollar; one dollar is 100 cents."),
    "refund_netting": (
        "Return gross event amounts minus settled refunds only. Count each event amount once, even with multiple refunds; pending refunds do not reduce the total.",
        "Return gross event amounts before refunds. Count every event amount exactly once."),
    "join_multiplicity": (
        "Sum the amount of each event having at least one target_tag record, counting each qualifying event once.",
        "Sum event amounts once for every matching target_tag record; repeated matching tag records each contribute."),
    "anti_join_nulls": (
        "Count directory customers with no matching event. A NULL customer ID in events matches no directory customer.",
        "Count directory customers with at least one matching event. A NULL customer ID in events matches no directory customer."),
    "weighted_rate": (
        "Return total successes divided by total trials across events, rounded to 6 decimal places, halfway cases away from zero.",
        "Return the unweighted mean of each event's successes/trials rate, rounded to 6 decimal places, halfway cases away from zero."),
    "group_threshold": (
        "Count customers whose sum of event amounts is at least threshold.",
        "Count customers having at least one individual event amount at least threshold."),
    "latest_snapshot": (
        "Sum the latest amount snapshot for each customer. Choose greatest activity_day, breaking same-day ties by greatest event_id.",
        "Sum the earliest amount snapshot for each customer. Choose smallest activity_day, breaking same-day ties by smallest event_id."),
    "left_join_zeros": (
        "Return the average total event amount per directory customer, including customers with no events as zero. Round to 6 decimal places, halfway cases away from zero.",
        "Return the average total event amount among directory customers having events; exclude customers with no events. Round to 6 decimal places, halfway cases away from zero."),
}
REQUEST_LOOKUP = {request: (family, mode) for family, requests in REQUESTS.items()
                  for mode, request in enumerate(requests)}


def profile(index):
    """Factors are relational normalization, time representation and query form."""
    if index not in range(8):
        raise ValueError("Unknown SQL layout profile")
    return {"normalized_customers": bool(index & 1), "integer_days": bool(index & 2),
            "cte": bool(index & 4)}


def day_value(day, integer):
    return day if integer else (date(2024, 1, 1) + timedelta(days=day)).isoformat()


def sql_literal(value):
    return str(value) if isinstance(value, int) else "'" + value.replace("'", "''") + "'"


def make_case(family, rng, layout):
    """Author a small business situation; no SQL is executed here."""
    base_day = rng.randrange(40, 550)
    n = rng.randrange(6, 13)
    customers = rng.sample(range(10, 900), 7)
    active_customers = 3 if family == "group_threshold" else rng.randrange(2, min(5, n - 2) + 1)
    rows = [{"event_id": i + 1, "customer_id": customers[i % active_customers],
             "activity_day": day_value(base_day + i, layout["integer_days"]),
             "amount": rng.randrange(2, 80)} for i in range(n)]
    aux, parameters = {}, {}
    if family == "extended_amount":
        for row in rows:
            row["quantity"] = rng.randrange(1, 7)
        rows[0]["quantity"] = 3
    elif family == "distinct_customers":
        rows[-1]["customer_id"] = None
        if n > 7 and rng.random() < .5:
            rows[-2]["customer_id"] = None
    elif family == "null_average":
        rows[0]["amount"] = None
        if rng.random() < .5:
            rows[1]["amount"] = 0
        for row in rows[2:]:
            if rng.random() < .3:
                row["amount"] = None
    elif family == "time_window":
        start = base_day + rng.randrange(1, 3)
        end = base_day + rng.randrange(4, 6)
        parameters = {"start_day": day_value(start, layout["integer_days"]),
                      "end_day": day_value(end, layout["integer_days"])}
        rows[0]["activity_day"] = parameters["start_day"]
        rows[1]["activity_day"] = parameters["end_day"]
    elif family == "unit_conversion":
        for i, row in enumerate(rows):
            row["unit"] = "dollar" if i % 2 else "cent"
    elif family == "refund_netting":
        # More than one settled refund creates genuine join fanout. One event
        # has no refund; a positive pending refund distinguishes its status.
        refunds = [(1, 2, "settled"), (1, 3, "settled"), (2, 7, "pending")]
        refunds += [(rng.randrange(2, n), rng.randrange(1, 8), rng.choice(["settled", "pending"]))
                    for _ in range(rng.randrange(1, 5))]
        aux["refunds"] = [{"refund_id": i + 1, "event_id": event,
                           "refund_amount": amount, "refund_status": status}
                          for i, (event, amount, status) in enumerate(refunds)]
        for row in rows:
            row["amount"] += 20
    elif family == "join_multiplicity":
        parameters["target_tag"] = rng.choice(["priority", "renewal", "wholesale", "partner"])
        tag = parameters["target_tag"]
        pairs = [(1, tag), (1, tag), (2, tag), (3, "other")]
        pairs += [(rng.randrange(3, n + 1), rng.choice([tag, "other"]))
                  for _ in range(rng.randrange(1, 5))]
        aux["tags"] = [{"tag_id": i + 1, "event_id": event, "tag": label}
                       for i, (event, label) in enumerate(pairs)]
        rows[1]["amount"] = rows[0]["amount"]  # DISTINCT amount loses an event.
    elif family in ("anti_join_nulls", "left_join_zeros"):
        aux["directory"] = [{"customer_id": c} for c in customers]
        if family == "anti_join_nulls":
            rows[-1]["customer_id"] = None
    elif family == "weighted_rate":
        for row in rows:
            row["trials"] = rng.randrange(2, 25)
            row["successes"] = rng.randrange(row["trials"] + 1)
        rows[0].update(trials=2, successes=1)
        rows[1].update(trials=20, successes=2)
    elif family == "group_threshold":
        threshold = rng.randrange(30, 80)
        parameters["threshold"] = threshold
        for row in rows:
            row["amount"] = rng.randrange(1, threshold // 3)
        rows[0]["amount"] = threshold - rng.randrange(1, 5)
        rows[3]["amount"] = rng.randrange(5, 10)  # Customer 0 crosses only when grouped.
        rows[1]["amount"] = threshold + 2
        rows[4]["amount"] = threshold + 1  # Customer 1 has two large events.
    elif family == "latest_snapshot":
        # Same-day ties use event_id, not amount or insertion order.
        rows[3]["customer_id"] = rows[0]["customer_id"]
        rows[3]["activity_day"] = rows[0]["activity_day"]
        rows[3]["amount"] = rows[0]["amount"] + rng.randrange(2, 20)
    elif family not in REQUESTS:
        raise ValueError("Unknown semantic family")
    rng.shuffle(rows)
    tables = {"events": rows, **aux}
    if layout["normalized_customers"]:
        mapping = {customer: i + 1 for i, customer in enumerate(customers)}
        tables["accounts"] = [{"account_ref": ref, "customer_id": customer}
                              for customer, ref in mapping.items()]
        for row in rows:
            customer = row.pop("customer_id")
            row["account_ref"] = mapping.get(customer)
    schemas = []
    for table, items in tables.items():
        columns = []
        for name in items[0]:
            kind = "TEXT" if name in ("refund_status", "unit", "tag") or (
                name == "activity_day" and not layout["integer_days"]) else "INTEGER"
            primary = name == {"events": "event_id", "accounts": "account_ref",
                               "refunds": "refund_id", "tags": "tag_id", "directory": "customer_id"}[table]
            columns.append(f"{name} {kind}" + (" PRIMARY KEY" if primary else ""))
        schemas.append(f"CREATE TABLE {table} ({', '.join(columns)});")
    return {"dialect": "SQLite", "schema": schemas, "tables": tables,
            "parameters": parameters,
            "data_contract": ("These are all rows, including duplicate tag records and explicit NULLs. "
                              "Dates are ISO YYYY-MM-DD strings." if not layout["integer_days"] else
                              "These are all rows, including duplicate tag records and explicit NULLs. "
                              "Dates are integer day offsets from 2024-01-01."),
            "output_contract": "Return one row with one value. The requested metric is numeric; SQL NULL is different from zero."}


def activity_rows(state):
    """Read business facts from visible tables; no metadata or SQL dependency."""
    tables = state["tables"]
    accounts = {r["account_ref"]: r["customer_id"] for r in tables.get("accounts", [])}
    rows = copy.deepcopy(tables["events"])
    for row in rows:
        if "account_ref" in row:
            row["customer_id"] = accounts.get(row.pop("account_ref"))
    return rows


def round_business(value, places):
    return float(Decimal(str(value)).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP))


def business_result(state):
    """Independent Python definition of each visible business request."""
    try:
        family, mode = REQUEST_LOOKUP[state["business_request"]]
    except (KeyError, TypeError) as error:
        raise ValueError("Unknown visible business request") from error
    rows, params, tables = activity_rows(state), state["parameters"], state["tables"]
    amounts = [r["amount"] for r in rows]
    if family == "extended_amount":
        value = sum(r["amount"] * r["quantity"] if mode == 0 else r["amount"] for r in rows)
    elif family == "distinct_customers":
        value = len({r["customer_id"] for r in rows if r["customer_id"] is not None}) if mode == 0 else len(rows)
    elif family == "null_average":
        known = [a for a in amounts if a is not None]
        value = round_business(sum(known) / (len(known) if mode == 0 else len(rows)), 6)
    elif family == "time_window":
        value = sum(r["amount"] for r in rows if params["start_day"] <= r["activity_day"] and (
            r["activity_day"] < params["end_day"] if mode == 0 else r["activity_day"] <= params["end_day"]))
    elif family == "unit_conversion":
        cents = sum(r["amount"] * (100 if r["unit"] == "dollar" else 1) for r in rows)
        value = cents if mode == 0 else round_business(cents / 100, 2)
    elif family == "refund_netting":
        value = sum(amounts) - (sum(r["refund_amount"] for r in tables["refunds"]
                                   if r["refund_status"] == "settled") if mode == 0 else 0)
    elif family == "join_multiplicity":
        counts = Counter(r["event_id"] for r in tables["tags"] if r["tag"] == params["target_tag"])
        value = sum(r["amount"] * (int(counts[r["event_id"]] > 0) if mode == 0 else counts[r["event_id"]])
                    for r in rows)
    elif family == "anti_join_nulls":
        present = {r["customer_id"] for r in rows if r["customer_id"] is not None}
        value = sum((r["customer_id"] not in present if mode == 0 else r["customer_id"] in present)
                    for r in tables["directory"])
    elif family == "weighted_rate":
        value = round_business(sum(r["successes"] for r in rows) / sum(r["trials"] for r in rows), 6) if mode == 0 else round_business(
            sum(r["successes"] / r["trials"] for r in rows) / len(rows), 6)
    elif family == "group_threshold":
        totals = defaultdict(int)
        for row in rows:
            totals[row["customer_id"]] += row["amount"]
        value = sum(amount >= params["threshold"] for amount in totals.values()) if mode == 0 else len(
            {r["customer_id"] for r in rows if r["amount"] >= params["threshold"]})
    elif family == "latest_snapshot":
        per_customer = defaultdict(list)
        for row in rows:
            per_customer[row["customer_id"]].append(row)
        choose = max if mode == 0 else min
        value = sum(choose(group, key=lambda r: (r["activity_day"], r["event_id"]))["amount"]
                    for group in per_customer.values())
    elif family == "left_join_zeros":
        totals = defaultdict(int)
        for row in rows:
            totals[row["customer_id"]] += row["amount"]
        included = [totals.get(r["customer_id"], 0) for r in tables["directory"]
                    if mode == 0 or r["customer_id"] in totals]
        value = round_business(sum(included) / len(included), 6)
    else:
        raise AssertionError(family)
    return [[value]]


def candidate_queries(family, state, layout):
    """Plausible distinct SQL operations; correctness is decided by execution."""
    p = state["parameters"]
    if family == "extended_amount":
        bodies = ["SELECT SUM(amount * quantity) FROM {L}", "SELECT SUM(amount) FROM {L}",
                  "SELECT SUM(DISTINCT amount * quantity) FROM {L}", "SELECT SUM(quantity) FROM {L}"]
    elif family == "distinct_customers":
        bodies = ["SELECT COUNT(DISTINCT customer_id) FROM {L}", "SELECT COUNT(*) FROM {L}",
                  "SELECT COUNT(customer_id) FROM {L}"]
    elif family == "null_average":
        bodies = ["SELECT ROUND(AVG(amount), 6) FROM {L}", "SELECT ROUND(AVG(COALESCE(amount, 0)), 6) FROM {L}",
                  "SELECT SUM(COALESCE(amount, 0)) FROM {L}", "SELECT ROUND(AVG(NULLIF(amount, 0)), 6) FROM {L}"]
    elif family == "time_window":
        a, b = sql_literal(p["start_day"]), sql_literal(p["end_day"])
        bodies = [f"SELECT COALESCE(SUM(amount), 0) FROM {{L}} WHERE activity_day >= {a} AND activity_day < {b}",
                  f"SELECT COALESCE(SUM(amount), 0) FROM {{L}} WHERE activity_day BETWEEN {a} AND {b}",
                  f"SELECT COALESCE(SUM(amount), 0) FROM {{L}} WHERE activity_day > {a} AND activity_day < {b}",
                  "SELECT COALESCE(SUM(amount), 0) FROM {L}"]
    elif family == "unit_conversion":
        conversion = "SUM(CASE WHEN unit = 'dollar' THEN amount * 100 ELSE amount END)"
        bodies = [f"SELECT {conversion} FROM {{L}}", f"SELECT ROUND({conversion} / 100.0, 2) FROM {{L}}",
                  "SELECT SUM(amount) FROM {L}", "SELECT SUM(amount) * 100 FROM {L}"]
    elif family == "refund_netting":
        gross = "(SELECT SUM(amount) FROM {L})"
        bodies = [f"SELECT {gross} - COALESCE((SELECT SUM(refund_amount) FROM refunds WHERE refund_status = 'settled'), 0)",
                  "SELECT SUM(amount) FROM {L}",
                  "SELECT SUM(e.amount) - COALESCE(SUM(r.refund_amount), 0) FROM {L} e LEFT JOIN refunds r ON e.event_id = r.event_id AND r.refund_status = 'settled'",
                  f"SELECT {gross} - COALESCE((SELECT SUM(refund_amount) FROM refunds), 0)"]
    elif family == "join_multiplicity":
        tag = sql_literal(p["target_tag"])
        bodies = [f"SELECT SUM(e.amount) FROM {{L}} e WHERE EXISTS (SELECT 1 FROM tags t WHERE t.event_id = e.event_id AND t.tag = {tag})",
                  f"SELECT SUM(e.amount) FROM {{L}} e JOIN tags t ON t.event_id = e.event_id WHERE t.tag = {tag}",
                  f"SELECT SUM(DISTINCT e.amount) FROM {{L}} e JOIN tags t ON t.event_id = e.event_id WHERE t.tag = {tag}",
                  "SELECT SUM(amount) FROM {L}"]
    elif family == "anti_join_nulls":
        exists = "(SELECT 1 FROM {L} e WHERE e.customer_id = d.customer_id)"
        bodies = ["SELECT COUNT(*) FROM directory d WHERE NOT EXISTS " + exists,
                  "SELECT COUNT(*) FROM directory d WHERE EXISTS " + exists,
                  "SELECT COUNT(*) FROM directory WHERE customer_id NOT IN (SELECT customer_id FROM {L})",
                  "SELECT COUNT(*) FROM directory d LEFT JOIN {L} e ON e.customer_id = d.customer_id WHERE e.event_id IS NULL"]
    elif family == "weighted_rate":
        bodies = ["SELECT ROUND(SUM(successes) * 1.0 / SUM(trials), 6) FROM {L}",
                  "SELECT ROUND(AVG(successes * 1.0 / trials), 6) FROM {L}",
                  "SELECT SUM(successes) / SUM(trials) FROM {L}",
                  "SELECT ROUND(SUM(successes) * 1.0 / COUNT(*), 6) FROM {L}"]
    elif family == "group_threshold":
        t = p["threshold"]
        bodies = [f"SELECT COUNT(*) FROM (SELECT customer_id FROM {{L}} GROUP BY customer_id HAVING SUM(amount) >= {t})",
                  f"SELECT COUNT(DISTINCT customer_id) FROM {{L}} WHERE amount >= {t}",
                  f"SELECT COUNT(*) FROM {{L}} WHERE amount >= {t}",
                  f"SELECT COUNT(*) FROM (SELECT customer_id FROM {{L}} GROUP BY customer_id HAVING AVG(amount) >= {t})"]
    elif family == "latest_snapshot":
        bodies = ["SELECT SUM(amount) FROM (SELECT amount, ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY activity_day DESC, event_id DESC) AS position FROM {L}) WHERE position = 1",
                  "SELECT SUM(amount) FROM (SELECT amount, ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY activity_day ASC, event_id ASC) AS position FROM {L}) WHERE position = 1",
                  "SELECT SUM(amount) FROM {L}",
                  "SELECT SUM(maximum) FROM (SELECT MAX(amount) AS maximum FROM {L} GROUP BY customer_id)"]
    elif family == "left_join_zeros":
        grouped = "(SELECT customer_id, SUM(amount) AS total FROM {L} GROUP BY customer_id)"
        bodies = [f"SELECT ROUND(AVG(COALESCE(e.total, 0)), 6) FROM directory d LEFT JOIN {grouped} e ON d.customer_id = e.customer_id",
                  f"SELECT ROUND(AVG(e.total), 6) FROM directory d JOIN {grouped} e ON d.customer_id = e.customer_id",
                  "SELECT ROUND(AVG(amount), 6) FROM {L}", "SELECT SUM(amount) FROM {L}"]
    else:
        raise ValueError("Unknown semantic family")
    columns = list(state["tables"]["events"][0])
    if layout["normalized_customers"]:
        projected = ["a.customer_id" if c == "account_ref" else "e." + c for c in columns]
        base = "SELECT " + ", ".join(projected) + " FROM events e LEFT JOIN accounts a ON e.account_ref = a.account_ref"
    else:
        base = "SELECT " + ", ".join(columns) + " FROM events"
    prefix = "WITH ledger AS (" + base + ") " if layout["cte"] else ""
    source = "ledger" if layout["cte"] else "(" + base + ")"
    return [prefix + body.replace("{L}", source) + ";" for body in bodies]


def database(state):
    """Only the complete visible schema and table rows initialize SQLite."""
    connection = sqlite3.connect(":memory:")
    try:
        for statement in state["schema"]:
            connection.execute(statement)
        for name, rows in state["tables"].items():
            if not rows:
                continue
            names = list(rows[0])
            if not all(part.replace("_", "").isalnum() for part in [name, *names]):
                raise ValueError("Invalid authored SQL identifier")
            connection.executemany(f"INSERT INTO {name} ({', '.join(names)}) VALUES ({', '.join('?' for _ in names)})",
                                   [[row[key] for key in names] for row in rows])
        connection.commit()
        connection.execute("PRAGMA query_only=ON")
        permitted = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_RECURSIVE}
        connection.set_authorizer(lambda action, *args: sqlite3.SQLITE_OK if action in permitted else sqlite3.SQLITE_DENY)
        return connection
    except Exception:
        connection.close()
        raise


def execute_candidates(state, options):
    result = []
    connection = database(state)
    try:
        # Bound deliberately malformed queries during validation, too.
        connection.set_progress_handler(lambda: 1, 1_000_000)
        for statement in options:
            if not statement.lstrip().upper().startswith(("SELECT ", "WITH ")):
                raise ValueError("Candidate is not a SELECT query")
            rows = [list(r) for r in connection.execute(statement).fetchall()]
            if len(rows) != 1 or len(rows[0]) != 1 or (rows[0][0] is not None and (
                    not isinstance(rows[0][0], (int, float)) or not math.isfinite(rows[0][0]))):
                raise ValueError("Candidate must produce one finite numeric or NULL value")
            result.append(rows)
    except (sqlite3.Error, sqlite3.Warning) as error:
        raise ValueError("Invalid candidate SQL: " + str(error)) from error
    finally:
        connection.close()
    return result


def target_for(state, options):
    expected = business_result(state)
    results = execute_candidates(state, options)
    matches = [result == expected for result in results]
    if not any(matches) or all(matches):
        raise ValueError("A decision needs both matching and nonmatching candidates")
    target = [float(match) / sum(matches) for match in matches]
    return target, expected, results


def generate(groups_per_family=64, seed=20260921):
    if not isinstance(groups_per_family, int) or not 1 <= groups_per_family <= 256:
        raise ValueError("groups_per_family must be between 1 and 256")
    seen_databases = set()
    for family in REQUESTS:
        for layout_index, split in enumerate(PROFILE_SPLITS):
            layout = profile(layout_index)
            family_id = f"{VERSION}:{family}:layout-{layout_index}"
            for index in range(groups_per_family):
                group = f"{family_id}:db-{index}"
                rng = random.Random(_hash([seed, group]))
                # Rejection is based only on visible answer/candidate evidence,
                # and applies equally to every split. Never keep accidental ties
                # between the two requested metrics as a counterfactual.
                for attempt in range(100):
                    state = make_case(family, rng, layout)
                    database_hash = _hash({"schema": state["schema"], "tables": state["tables"]})
                    if database_hash in seen_databases:
                        continue
                    options = candidate_queries(family, state, layout)
                    rng.shuffle(options)
                    variants = []
                    for mode, request in enumerate(REQUESTS[family]):
                        current = copy.deepcopy(state)
                        current["business_request"] = request
                        target, expected, results = target_for(current, options)
                        variants.append((current, target, expected, results))
                    if variants[0][2] != variants[1][2]:
                        break
                else:
                    raise ValueError("Could not generate a distinguishing warehouse: " + group)
                seen_databases.add(database_hash)
                for mode, (current, target, expected, results) in enumerate(variants):
                    yield {"id": group + f":request-{mode}", "group_id": group, "split": split,
                           "source": VERSION, "kind": "choice", "state": current,
                           "question": QUESTION, "options": list(options), "target": target,
                           "metadata": {"family": "evidence", "domain": "sql_business_semantics",
                               "language": "en", "template_id": family_id,
                               "semantic_operator": family, "structural_family": family_id,
                               "layout": layout, "source_instance_id": group,
                               "database_sha256": database_hash, "context_sha256": _hash(current),
                               "reference_result": expected, "candidate_results": results,
                               "target_basis": "independent_python_business_result_and_sqlite_answer_equivalence",
                               "counterfactual": {"parent_variant": 0, "changed_field": "business_request"} if mode else None,
                               "provenance": {"type": "synthetic", "license": "CC0-1.0",
                                   "generator_version": VERSION, "seed": seed, "group_index": index,
                                   "variant": mode, "split_policy": SPLIT_POLICY,
                                   "inspiration_url": INSPIRATION, "external_examples_imported": False,
                                   "generation_attempt": attempt + 1}}}


def query_template_hash(options):
    """Count query-form diversity separately from operator/schema families."""
    templates = [re.sub(r"'[^']*'|\b\d+(?:\.\d+)?\b", "?", query) for query in options]
    return _hash(sorted(templates))


def audit_records(records):
    rows = list(records)
    summary = validate_records(rows)
    membership = {key: {} for key in ("structural_family", "database_sha256", "source_instance_id", "context_sha256")}
    groups = defaultdict(list)
    positions = Counter()
    equivalents = Counter()
    maximum_chars = 0
    for row in rows:
        if not 3 <= len(row["options"]) <= 5:
            raise ValueError("Candidate fanout exceeds the bounded SQL profile")
        target, expected, results = target_for(row["state"], row["options"])
        if row["target"] != target or row["metadata"]["reference_result"] != expected or row["metadata"]["candidate_results"] != results:
            raise ValueError("SQL label or saved result differs from independent execution")
        for key, splits in membership.items():
            value = row["metadata"][key]
            if value in splits and splits[value] != row["split"]:
                raise ValueError("SQL family/database/context crosses splits")
            splits[value] = row["split"]
        actual_hash = _hash({"schema": row["state"]["schema"], "tables": row["state"]["tables"]})
        if actual_hash != row["metadata"]["database_sha256"] or _hash(row["state"]) != row["metadata"]["context_sha256"]:
            raise ValueError("Visible SQL data fingerprint differs")
        groups[row["group_id"]].append(row)
        equivalents[sum(p > 0 for p in target)] += 1
        positions.update({i: p for i, p in enumerate(target) if p})
        maximum_chars = max(maximum_chars, len(json.dumps({k: row[k] for k in ("state", "question", "kind", "options")})))
    if len(membership["context_sha256"]) != len(rows):
        raise ValueError("SQL contexts were duplicated")
    for group in groups.values():
        group.sort(key=lambda r: r["metadata"]["provenance"]["variant"])
        if len(group) != 2 or group[0]["options"] != group[1]["options"]:
            raise ValueError("Counterfactual needs two requests with fixed candidates")
        first, second = group
        changed = [key for key in first["state"] if first["state"][key] != second["state"][key]]
        if changed != ["business_request"] or first["target"] == second["target"] or business_result(first["state"]) == business_result(second["state"]):
            raise ValueError("Counterfactual does not change the visible requested answer")
    return {"summary": summary, "unique_databases": len(membership["database_sha256"]),
            "counterfactual_groups": len(groups), "single_request_counterfactual_edges": len(groups),
            "unique_contexts": len(membership["context_sha256"]),
            "sql_structural_families": len(membership["structural_family"]),
            "unique_candidate_sql_template_sets": len({query_template_hash(r["options"]) for r in rows}),
            "semantic_operators": dict(Counter(r["metadata"]["semantic_operator"] for r in rows)),
            "candidate_count_distribution": dict(sorted(Counter(len(r["options"]) for r in rows).items())),
            "equivalent_candidate_count_distribution": dict(sorted(equivalents.items())),
            "probability_mass_by_candidate_position": dict(sorted(positions.items())),
            "largest_full_model_input_characters": maximum_chars,
            "sqlite_version": sqlite3.sqlite_version,
            "checks": {"every_candidate_executes": True, "python_sqlite_answers_agree": True,
                       "equivalent_correct_candidates_share_target": True, "every_zero_target_differs_on_visible_rows": True,
                       "counterfactual_changes_only_request_and_changes_answer": True,
                       "parent_database_and_structural_family_split_disjoint": True,
                       "unique_visible_databases_and_contexts": True, "all_queries_read_only": True}}


def build_dataset(output_dir, groups_per_family=64, seed=20260921):
    output = Path(output_dir)
    if output.is_symlink() or output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("Choose a new empty SQL output directory")
    rows = list(generate(groups_per_family, seed))
    audit = audit_records(rows)
    manifest = _write_dataset(rows, output, {"type": "synthetic", "generator_version": VERSION,
        "groups_per_family": groups_per_family, "seed": seed, "license": "CC0-1.0",
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "inspiration_url": INSPIRATION, "split_policy": SPLIT_POLICY,
        "external_examples_imported": False, "benchmark_inputs_read": False, "paid_calls": 0,
        "layout_profiles": [{**profile(i), "split": s} for i, s in enumerate(PROFILE_SPLITS)]})
    manifest.update(audit)
    manifest["scope"] = ("Original complete toy SQLite warehouses for 12 business-semantic operators. "
        "96 operator/layout combinations at full size are structural families, not 96 independently collected domains. "
        "Two related metric requests share each database; decision rows are not independent database instances.")
    manifest["limitations"] = [
        "Correctness means exact scalar answer equivalence on the fully visible finite database, not SQL equivalence on every possible database.",
        "OOD holds out normalized-customer + integer-day + CTE combinations within the authored grammar; semantic operators are shared across splits.",
        "Customers-normalization and timestamp representation change schema; CTE versus derived relation is a query-form factor, not a new business domain.",
        "English metric definitions are controlled original language, not naturally collected business stakeholder requests or dbt-assay examples.",
        "Single-request counterfactuals change the requested metric; they are not table-cell mutations or independently collected warehouses.",
        "SQLite scalar tasks do not establish arbitrary SQL dialect, large warehouse, DDL, security-audit or natural text-to-SQL capability.",
        "Rounded decimal requests are compared exactly after the specified rounding; NULL and zero are distinct.",
        "No model inference, training or benchmark improvement is established by this dataset."]
    manifest.update(training_performed=False, model_inference_performed=False)
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--groups-per-family", type=int, default=64)
    parser.add_argument("--seed", type=int, default=20260921)
    args = parser.parse_args()
    report = build_dataset(args.output_dir, args.groups_per_family, args.seed)
    print(json.dumps({key: report[key] for key in ("summary", "unique_databases", "sql_structural_families",
                                                  "candidate_count_distribution", "checks")}, indent=2))


if __name__ == "__main__":
    main()
