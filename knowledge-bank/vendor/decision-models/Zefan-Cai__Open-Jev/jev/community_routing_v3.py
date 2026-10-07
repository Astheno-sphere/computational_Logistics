"""Pinned human intent labels as bounded Choice/Noul routing contracts.

Official held-out utterance groups are reserved globally before conversion.
Full-catalog evaluation is a separate protocol, never a training expansion.
"""
import argparse
from collections import Counter, defaultdict
import csv
from functools import lru_cache
import hashlib
import io
import json
from pathlib import Path
import random
import re
import unicodedata

from .data import _write_dataset


VERSION = "community-routing-v3"
ABSTAIN = "__abstain__"
OOS = "oos"
SIZES = (2, 4, 8)
SOURCES = {
    "banking77": {
        "repository": "PolyAI-LDN/task-specific-datasets",
        "revision": "57ec275d8078af65b7731c2a98be812d844a6d6b",
        "license": "CC-BY-4.0", "catalog": "BANKING77 banking support intents",
        "attribution": "Casanueva et al. (2020), Efficient Intent Detection with Dual Sentence Encoders, PolyAI BANKING77",
        "intent_count": 77,
        "files": {
            "banking-train.csv": {"path": "banking_data/train.csv", "sha256": "b06e26ac675513959a63135f11b94ea7786ed02da65db93a5650d8838cbc664b", "split": "train", "rows": 10003},
            "banking-test.csv": {"path": "banking_data/test.csv", "sha256": "d12d6e3bc4c3103966ae786dc435913c0c563dfa328f5a3646d0e62cfeeb474d", "split": "test", "rows": 3080},
        },
    },
    "clinc150": {
        "repository": "clinc/oos-eval", "revision": "828f8093932c8fe6ca7936c3d2e52903b1c523de",
        "license": "CC-BY-3.0", "catalog": "CLINC150 assistant intents",
        "attribution": "Larson et al. (2019), An Evaluation Dataset for Intent Classification and Out-of-Scope Prediction, CLINC150",
        "intent_count": 150,
        "files": {"clinc-data-full.json": {"path": "data/data_full.json", "sha256": "36923c3705a59e08fe9c3883d8bc2dd966ef93e22cb78ac41171782a698d56e0"}},
        "split_counts": {"train": 15000, "val": 3000, "test": 4500, "oos_train": 100, "oos_val": 100, "oos_test": 1000},
    },
}
EXPANSIONS = {
    "routing": "look up a bank routing number", "text": "send a text message",
    "gas": "find a gas station", "gas_type": "identify the required fuel type",
    "order": "place an order", "cancel": "cancel the current assistant action",
    "yes": "confirm or answer yes", "no": "decline or answer no",
    "maybe": "express uncertainty or answer maybe", "repeat": "repeat the last response",
    "accept_reservations": "ask whether a restaurant accepts reservations",
    "mpg": "check vehicle fuel economy in miles per gallon",
    "apr": "check the annual percentage rate", "food_last": "check food shelf life",
    "min_payment": "check the minimum payment", "w2": "get a W-2 tax form",
    "rollover_401k": "roll over a 401(k) retirement account",
}
CHOICE_QUESTION = ("Route the request using the named catalog. Choose the available handler for its intent. "
                   "Abstain if the matching handler is unavailable or the request is outside this catalog. "
                   "Classify the request; do not perform it.")
NOUL_QUESTION = ("Does the proposed handler match this request's intent in the named catalog? "
                 "Answer no if the request is outside the catalog. Classify the request; do not perform it.")
SPLIT_POLICY = "global_normalized_utterance_reserve_official_test_then_val; source_train_85_5_5_5; official_val_50_50_calibration_validation"


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def normalize(value):
    return " ".join(re.findall(r"\w+", unicodedata.normalize("NFKC", value).casefold().replace("_", " ")))


def option_text(label):
    if label == ABSTAIN:
        return "Abstain: no matching handler is available"
    phrase = EXPANSIONS.get(label, label.replace("_", " ").strip("?"))
    phrase = re.sub(r"\b(pin|atm|pto|ai)\b", lambda match: match[0].upper(), phrase, flags=re.I)
    return "Handle requests about: " + phrase


def source_file(dataset, split):
    info = SOURCES[dataset]
    name = "clinc-data-full.json" if dataset == "clinc150" else "banking-" + split + ".csv"
    file = info["files"][name]
    return {"input_sha256": file["sha256"],
            "source_url": f"https://raw.githubusercontent.com/{info['repository']}/{info['revision']}/{file['path']}"}


def load_sources(directory):
    loaded = {}
    for dataset, info in SOURCES.items():
        splits = {}
        for filename, file in info["files"].items():
            raw = (Path(directory) / filename).read_bytes()
            if hashlib.sha256(raw).hexdigest() != file["sha256"]:
                raise ValueError("Pinned source checksum differs: " + filename)
            if filename.endswith(".csv"):
                parsed = list(csv.DictReader(io.StringIO(raw.decode())))
                if len(parsed) != file["rows"] or any(set(row) != {"text", "category"} for row in parsed):
                    raise ValueError("BANKING77 source schema/count differs")
                splits[file["split"]] = [{"text": row["text"], "label": row["category"], "id": str(i)} for i, row in enumerate(parsed)]
            else:
                parsed = json.loads(raw)
                if {key: len(value) for key, value in parsed.items()} != info["split_counts"]:
                    raise ValueError("CLINC source split counts differ")
                for split, values in parsed.items():
                    if any(not isinstance(row, list) or len(row) != 2 for row in values):
                        raise ValueError("CLINC source schema differs")
                    splits[split] = [{"text": row[0], "label": row[1], "id": str(i)} for i, row in enumerate(values)]
        if len({row["label"] for row in splits["train"]}) != info["intent_count"]:
            raise ValueError("Published intent inventory differs")
        loaded[dataset] = splits
    return loaded


def split_role(split):
    return "test" if split.endswith("test") else "val" if split.endswith("val") else "train"


def prepare_utterances(sources, seed):
    """Reserve shared held-out components before dropping duplicates/conflicts."""
    catalogs, raw_rows, labels, components = {}, [], defaultdict(set), defaultdict(list)
    for dataset, splits in sources.items():
        if dataset not in SOURCES or "train" not in splits:
            raise ValueError("Unknown source or missing official training split")
        catalogs[dataset] = sorted({row["label"] for row in splits["train"] if row["label"] != OOS})
        if len(catalogs[dataset]) < max(SIZES) or len({option_text(label) for label in catalogs[dataset]}) != len(catalogs[dataset]):
            raise ValueError("Catalog must have at least eight distinct readable intent names")
        for split, rows in splits.items():
            if split not in {"train", "val", "test", "oos_train", "oos_val", "oos_test"}:
                raise ValueError("Unknown official split")
            for row in rows:
                if (any(not isinstance(row.get(key), str) or not row[key].strip() for key in ("text", "label", "id"))
                        or row["label"] not in [*catalogs[dataset], OOS]
                        or (dataset == "banking77" and row["label"] == OOS)):
                    raise ValueError("Malformed human-labeled routing example")
                norm = normalize(row["text"])
                if not norm:
                    raise ValueError("Empty normalized utterance")
                item = {**row, "dataset": dataset, "original_split": split, "normalized": norm}
                raw_rows.append(item)
                labels[dataset, norm].add(row["label"])
                components[norm].append(item)
    reserved_test = {row["normalized"] for row in raw_rows if split_role(row["original_split"]) == "test"}
    reserved_val = {row["normalized"] for row in raw_rows if split_role(row["original_split"]) == "val"}
    reserved_heldout = reserved_test | reserved_val
    removed, seen, kept = Counter(), set(), []
    for row in sorted(raw_rows, key=lambda row: (row["dataset"], row["normalized"], row["text"], row["original_split"], row["id"])):
        norm, dataset = row["normalized"], row["dataset"]
        role = split_role(row["original_split"])
        if role == "train" and norm in reserved_heldout:
            removed["official_heldout_group_reserved_from_train"] += 1
            continue
        if role == "val" and norm in reserved_test:
            removed["official_test_group_reserved_from_validation"] += 1
            continue
        if len(labels[dataset, norm]) != 1:
            removed["conflicting_labels_within_catalog"] += 1
            continue
        if (dataset, norm) in seen:
            removed["duplicate_utterance_within_catalog"] += 1
            continue
        seen.add((dataset, norm))
        bucket = int(digest(f"{seed}:{norm}")[:16], 16) % 100
        if role == "test":
            split = "test"
        elif role == "val":
            split = "calibration" if bucket < 50 else "validation"
        else:
            split = "train" if bucket < 85 else "calibration" if bucket < 90 else "validation" if bucket < 95 else "ood"
        kept.append({**row, "split": split, "group_id": VERSION + ":utterance:" + digest(norm)})
    cross_source = []
    for norm, values in sorted(components.items()):
        binding = {dataset: sorted(labels[dataset, norm]) for dataset in {row["dataset"] for row in values}}
        if len(binding) > 1:
            cross_source.append({"normalized_utterance_sha256": digest(norm), "catalog_labels": binding,
                                 "official_roles": sorted({split_role(row["original_split"]) for row in values})})
    audit = {"raw_rows": len(raw_rows), "retained_catalog_utterances": len(kept),
             "retained_global_utterance_groups": len({row["normalized"] for row in kept}),
             "removed": dict(removed), "cross_source_components": cross_source,
             "cross_source_label_policy": "Labels belong to distinct named catalogs; different spellings are reported, not automatically adjudicated as semantic conflicts. Within-catalog conflicts are excluded; shared groups keep one split globally."}
    return sorted(kept, key=lambda row: (row["dataset"], row["split"], digest(f"{seed}:{row['normalized']}"))), catalogs, audit


@lru_cache(maxsize=4096)
def label_tokens(value):
    aliases = {"payments": "pay", "payment": "pay", "paying": "pay", "charged": "charge",
               "charges": "charge", "fees": "fee", "withdrawals": "withdrawal", "getting": "get"}
    stop = {"handle", "requests", "about", "a", "the", "my", "of", "to", "by", "or", "via"}
    return frozenset(aliases.get(token, token) for token in normalize(value).split() if token not in stop)


def negatives(catalog, gold, text, count, rng):
    available = [label for label in catalog if label != gold]
    if count > len(available):
        raise ValueError("Not enough distinct negative handlers")
    query = label_tokens(option_text(gold) if gold != OOS else text)
    ranked = []
    for label in available:
        tokens = label_tokens(option_text(label))
        overlap = len(query & tokens) / max(1, len(query | tokens))
        ranked.append((overlap, rng.random(), label))
    hard = [label for score, _, label in sorted(ranked, reverse=True) if score > 0][:(count+1)//2]
    remaining = [label for label in available if label not in hard]
    random_labels = rng.sample(remaining, count-len(hard))
    return hard + random_labels, {"intent_name_overlap": len(hard), "random": len(random_labels)}


def make_record(row, view, state, question, kind, option_labels, answer, selection):
    info = SOURCES[row["dataset"]]
    options = ["no", "yes"] if kind == "noul" else [option_text(label) for label in option_labels]
    provenance = {"type": "import", "license": info["license"], "attribution": info["attribution"],
                  "revision": info["revision"], **source_file(row["dataset"], row["original_split"]),
                  "original_id": row["original_split"] + ":" + row["id"], "original_split": row["original_split"],
                  "original_label": row["label"], "split_policy": SPLIT_POLICY,
                  "conversion": "Human intent gold retained; options and query contract transformed deterministically."}
    return {"id": VERSION + ":" + row["dataset"] + ":" + digest(row["normalized"]) + ":" + view,
            "group_id": row["group_id"], "source": row["dataset"] + "-routing-v3", "split": row["split"],
            "state": state, "question": question, "kind": kind, "options": options,
            "target": [float(label == answer) for label in (["no", "yes"] if kind == "noul" else option_labels)],
            "metadata": {"family": "semantic_routing", "language": "en", "dataset": row["dataset"],
                         "view": view, "target_basis": "published_human_intent_label_with_explicit_catalog_contract",
                         "option_label_ids": option_labels, "negative_selection": selection,
                         "ood_scope": "held_out_original_train_utterance_groups_within_source",
                         "provenance": provenance}}


def convert_rows(sources, seed=20260921):
    kept, catalogs, audit = prepare_utterances(sources, seed)
    buckets = defaultdict(list)
    for row in kept:
        buckets[row["dataset"], row["split"]].append(row)
    positions, result, view_sizes = Counter(), [], Counter()
    for (dataset, split), utterances in sorted(buckets.items()):
        # OOS has no positive handler. Allocate positives from in-scope rows so
        # the one-Noul-per-utterance views are balanced whenever feasible.
        in_scope = sorted([row for row in utterances if row["label"] != OOS], key=lambda row: digest(f"{seed}:noul:{row['group_id']}"))
        positive_groups = {row["group_id"] for row in in_scope[:len(utterances)//2]}
        for index, row in enumerate(utterances):
            size, gold = SIZES[index % len(SIZES)], row["label"]
            state = {"utterance": row["text"], "catalog": SOURCES[dataset]["catalog"]}
            views = ("choice_present", "choice_omitted") if gold != OOS else ("choice_out_of_scope",)
            for view in views:
                present = view == "choice_present"
                rng = random.Random(digest(f"{seed}:{row['group_id']}:{dataset}:{view}"))
                selected, selection = negatives(catalogs[dataset], gold, row["text"], size-2 if present else size-1, rng)
                key = (dataset, split, view, size)
                ordinal = positions[key]
                positions[key] += 1
                target_index = ordinal % size
                labels = [None] * size
                answer = gold if present else ABSTAIN
                labels[target_index] = answer
                if present:
                    labels[(target_index+1+(ordinal//size) % (size-1)) % size] = ABSTAIN
                rng.shuffle(selected)
                iterator = iter(selected)
                labels = [next(iterator) if label is None else label for label in labels]
                result.append(make_record(row, view, state, CHOICE_QUESTION, "choice", labels, answer, selection))
                view_sizes[f"{dataset}/{split}/{view}/{size}"] += 1
            positive = row["group_id"] in positive_groups
            if positive:
                candidate, selection = gold, {"intent_name_overlap": 0, "random": 0}
            else:
                rng = random.Random(digest(f"{seed}:{row['group_id']}:{dataset}:noul"))
                candidates, selection = negatives(catalogs[dataset], gold, row["text"], 1, rng)
                candidate = candidates[0]
            result.append(make_record(row, "noul_candidate", {**state, "proposed_handler": option_text(candidate)},
                                      NOUL_QUESTION, "noul", [candidate], "yes" if positive else "no", selection))
    audit.update(decision_rows=len(result), view_sizes=dict(sorted(view_sizes.items())),
                 unique_utterances_by_source_split={f"{source}/{split}": len(rows) for (source, split), rows in sorted(buckets.items())},
                 noul_positive_negative={f"{source}/{split}": dict(Counter("yes" if row["target"][1] else "no" for row in result if row["kind"] == "noul" and row["metadata"]["dataset"] == source and row["split"] == split)) for source, split in sorted(buckets)})
    protocols = {}
    for dataset, catalog in catalogs.items():
        original_test = [row for row in kept if row["dataset"] == dataset and split_role(row["original_split"]) == "test"]
        labels = [*catalog, ABSTAIN] if dataset == "clinc150" else list(catalog)
        protocols[dataset] = {"status": "prepared_not_evaluated", "evaluation_only": True,
                              "candidate_count": len(labels), "catalog": {label: option_text(label) for label in labels},
                              "official_test_utterances_after_screening": len(original_test),
                              "eligible_original_ids": [row["original_split"] + ":" + row["id"] for row in original_test],
                              "gold_rule": "Original human intent ID; CLINC oos maps to abstain.",
                              "source_binding": SOURCES[dataset],
                              "construction": "Load only eligible official-test source IDs at the pinned file hashes and attach this full catalog. Do not read this protocol as a training split."}
    return result, audit, protocols


def build(source, output, seed=20260921):
    source, output = Path(source), Path(output)
    if source.resolve() == output.resolve() or source.resolve().is_relative_to(output.resolve()):
        raise ValueError("Output must not contain or replace the pinned source directory")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("Routing output must be a new or empty directory")
    sources = load_sources(source)
    rows, audit, protocols = convert_rows(sources, seed)
    manifest = _write_dataset(rows, output, {"type": "import", "version": VERSION, "seed": seed,
        "datasets": SOURCES, "source_counts": {name: {split: len(values) for split, values in splits.items()} for name, splits in sources.items()},
        "normalization": "NFKC, Unicode casefold, word tokens, collapsed whitespace; raw utterances unchanged.",
        "candidate_sizes_including_abstain": list(SIZES), "views_per_in_scope_utterance": 3,
        "views_per_oos_utterance": 2, "audit": audit,
        "limitations": ["Exactly two independently labeled datasets, not 151 domains.",
                        "Candidate subsets are constructed using source gold; subset accuracy is not original full-catalog accuracy.",
                        "Hard negatives use readable intent-name token overlap, not an embedding semantic model.",
                        "Human intent labels and readable descriptions may be ambiguous or imperfect.",
                        "Within-source utterance OOD does not establish new-intent or new-domain generalization.",
                        "No benchmark requests, GPU training, or model quality measurements are performed."]})
    (output / "full-catalog-eval-only.json").write_text(json.dumps(protocols, indent=2, ensure_ascii=False) + "\n")
    return manifest, protocols


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--seed", type=int, default=20260921)
    args = parser.parse_args()
    manifest, _ = build(args.source_dir, args.output_dir, args.seed)
    print(json.dumps({"summary": manifest["summary"], "audit": manifest["configuration"]["audit"]}, indent=2))


if __name__ == "__main__":
    main()
