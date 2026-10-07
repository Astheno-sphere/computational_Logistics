"""Freeze original synthetic counterfactual controls, with oracle audit."""
import argparse
import json
from jev.frontier_controls_v4 import build


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--groups-per-family", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20261002)
    args = parser.parse_args()
    manifest = build(args.output, args.groups_per_family, args.seed)
    print(json.dumps(manifest["oracle_audit"], indent=2))


if __name__ == "__main__":
    main()
