"""Freeze 96 original policy groups, without training or importing upstream rows."""
import argparse
import json

from jev.policy_controls_v6 import build


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", type=int, default=20261002)
    args = parser.parse_args()
    manifest = build(args.output, args.seed)
    print(json.dumps(manifest["oracle_audit"], indent=2))


if __name__ == "__main__":
    main()
