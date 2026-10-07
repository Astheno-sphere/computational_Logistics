"""Prove the small mailroom probe is byte-preserved inside the full corpus."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compare(small, large):
    small, large = Path(small), Path(large)
    manifests = [json.loads((directory / "manifest.json").read_text()) for directory in (small, large)]
    preserved = {}
    for name in manifests[0]["files_sha256"]:
        if any(sha(directory / name) != manifest["files_sha256"][name] for directory, manifest in zip((small, large), manifests)):
            raise ValueError("Sealed input file hash differs")
        wanted = {json.loads(line)["id"]: line for line in (small / name).read_bytes().splitlines(keepends=True)}
        seen = set()
        with (large / name).open("rb") as stream:
            for line in stream:
                identifier = json.loads(line)["id"]
                if identifier not in wanted:
                    continue
                if identifier in seen or line != wanted[identifier]:
                    raise ValueError("An old row/case changed bytes or was duplicated")
                seen.add(identifier)
        if seen != set(wanted):
            raise ValueError("An old row/case disappeared or moved to another split")
        preserved[name] = len(seen)
    if manifests[0]["configuration"]["generator_sha256"] != manifests[1]["configuration"]["generator_sha256"]:
        raise ValueError("Generator changed during expansion")
    return {"verified": True, "small_groups": manifests[0]["configuration"]["groups"],
            "large_groups": manifests[1]["configuration"]["groups"], "preserved_in_same_files": preserved,
            "small_manifest_sha256": sha(small / "manifest.json"), "large_manifest_sha256": sha(large / "manifest.json"),
            "generator_sha256": manifests[0]["configuration"]["generator_sha256"],
            "meaning": "Every small-corpus JSONL line occurs byte-identically, exactly once, in the same full-corpus file. Thus test/OOD requests and rows never move to train. Full-corpus additional holdout families do not alter the frozen probe selection.",
            "model_outputs_consulted": False, "verifier_sha256": sha(__file__)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--small", required=True, type=Path)
    parser.add_argument("--large", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists() or any(args.output.resolve().is_relative_to(directory.resolve()) for directory in (args.small, args.large)):
        parser.error("Choose a new report path outside both input corpora")
    result = compare(args.small, args.large)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
