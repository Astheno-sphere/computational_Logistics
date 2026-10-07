"""Original closed-interval time controls; no benchmark items are imported."""
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import random

from .data import SPLITS, _write_dataset


VERSION = "temporal-windows-v5"
POLICY = ("Accept from delivery through delivery plus the stated hours, including both endpoints. "
          "Reject outside this window. An approved exception overrides either outcome with review. "
          "Compare absolute instants using the explicit fixed UTC offsets.")
OOD_POLICY = ("The permitted interval starts at delivery and ends the stated number of hours later; "
              "both limits are included. Outside it, reject. If an exception is approved, use review instead. "
              "Displayed local dates and clocks must be interpreted with their fixed UTC offsets.")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def outcome(state):
    start = datetime.fromisoformat(state["delivered_at"])
    request = datetime.fromisoformat(state["request_received_at"])
    if state["exception_approved"]:
        return "review"
    return "accept" if start <= request <= start + timedelta(hours=state["return_window_hours"]) else "reject"


def records(train_groups=32, eval_groups=8, seed=20261002):
    if any(type(n) is not int or n < 8 or n % 8 for n in (train_groups, eval_groups)):
        raise ValueError("Group counts must be positive multiples of eight")
    for split in SPLITS:
        ood = split == "ood"
        offsets = (-345, 525, 765) if ood else (-480, 0, 330)
        anchors = ((2, 28), (2, 29), (12, 31)) if ood else ((1, 31), (2, 28), (12, 31))
        years = (2028, 2032, 2036, 2040) if ood else tuple(year for year in range(2025, 2100) if year % 4)
        windows = (7, 31, 73) if ood else (1, 25, 49)
        for index in range(train_groups if split == "train" else eval_groups):
            group = f"{VERSION}/{split}/{index}"
            rng = random.Random(digest([seed, group]))
            start = datetime(rng.choice(years), *anchors[index % 3], 23,
                             rng.randrange(60), rng.randrange(60), tzinfo=timezone.utc)
            hours = windows[index % 3]
            deadline = start + timedelta(hours=hours)
            edge = start if index % 2 == 0 else deadline
            delivery_zone = timezone(timedelta(minutes=offsets[index % 3]))
            request_zone = timezone(timedelta(minutes=offsets[(index + 1) % 3]))
            base = {"case": "case-" + digest([seed, group])[:16],
                    "delivered_at": start.astimezone(delivery_zone).isoformat(),
                    "return_window_hours": hours, "exception_approved": False,
                    "policy": OOD_POLICY if ood else POLICY}
            instants = (edge - timedelta(seconds=1), edge, edge + timedelta(seconds=1),
                        deadline + timedelta(seconds=1))
            for variant, instant in enumerate(instants):
                state = copy.deepcopy(base)
                state["request_received_at"] = instant.astimezone(request_zone).isoformat()
                state["exception_approved"] = variant == 3
                answer = outcome(state)
                # Rotate the verification row so type does not reveal the edge or exception.
                kind = "noul" if variant == index % 4 else "choice"
                proposed = None
                if kind == "noul":
                    proposed = answer if (index // 4) % 2 == 0 else rng.choice([x for x in ("accept", "reject", "review") if x != answer])
                    question = f"Does the supplied policy establish the outcome '{proposed}'? Determine the route from the request and delivery timestamps."
                    options = ["no", "yes"]
                    target = [float(answer != proposed), float(answer == proposed)]
                else:
                    question = "Resolve the request under the explicit window and exception rule." if ood else "Which route follows this return-window policy?"
                    options = ["accept", "reject", "review"]
                    rng.shuffle(options)
                    target = [float(option == answer) for option in options]
                yield {"id": group + f"/v{variant}", "group_id": group, "split": split,
                       "source": VERSION, "state": state, "question": question, "kind": kind,
                       "options": options, "target": target, "metadata": {
                           "family": "policy", "scenario_family": "timeline",
                           "template_id": VERSION + ("/ood" if ood else "/id"),
                           "entity_ids": [state["case"]], "proposed_outcome": proposed,
                           "target_basis": "closed_interval_datetime_oracle",
                           "provenance": {"type": "synthetic", "license": "CC0-1.0",
                                          "generator_version": VERSION, "seed": seed,
                                          "group_index": index, "variant": variant,
                                          "split_policy": "complete_four_row_groups_with_disjoint_case_ids"}}}


def build(output, train_groups=32, eval_groups=8, seed=20261002):
    output = Path(output)
    if output.exists():
        raise FileExistsError("Refusing to overwrite a frozen dataset")
    rows = list(records(train_groups, eval_groups, seed))
    manifest = _write_dataset(rows, output, {"type": "synthetic", "generator_version": VERSION,
                                            "train_groups": train_groups, "eval_groups": eval_groups,
                                            "seed": seed, "license": "CC0-1.0",
                                            "scope": "Original temporal-window controls; no benchmark text or gold; no model evaluation"})
    manifest["generator_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest
