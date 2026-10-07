"""Freeze small original time-window controls without training a model."""
import argparse
import json

from jev.temporal_windows_v5 import build


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--train-groups", type=int, default=32)
    parser.add_argument("--eval-groups", type=int, default=8)
    parser.add_argument("--seed", type=int, default=20261002)
    args = parser.parse_args()
    print(json.dumps(build(args.output, args.train_groups, args.eval_groups, args.seed), indent=2))


if __name__ == "__main__":
    main()
