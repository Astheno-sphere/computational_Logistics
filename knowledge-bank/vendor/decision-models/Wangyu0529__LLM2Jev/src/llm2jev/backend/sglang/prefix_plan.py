"""Plan complete-candidate submissions; KV storage belongs to the engine."""

from collections.abc import Sequence


def staged_batches(input_ids: Sequence[Sequence[int]]) -> list[list[int]]:
    """Seed shared token paths before submitting their remaining branches.

    Each index appears once. Only tokens before the final scoring token are
    considered reusable. Groups contain an unseeded branch and a known common
    length; selecting a real candidate seeds its whole path for the next round.
    No text boundaries, question IDs, or current engine cache state are assumed.
    """
    roots: dict[int, list[int]] = {}
    ready: list[int] = []
    for index, tokens in enumerate(input_ids):
        if len(tokens) <= 1:
            ready.append(index)
        else:
            roots.setdefault(tokens[0], []).append(index)
    groups = [(indices, 1) for indices in roots.values()]
    batches: list[list[int]] = []
    while groups or ready:
        batch = ready
        ready = []
        following = []
        for indices, common in groups:
            representative = indices[0]
            batch.append(representative)
            seed = input_ids[representative]
            branches: dict[tuple[int, int], list[int]] = {}
            for index in indices[1:]:
                tokens = input_ids[index]
                shared = common
                limit = min(len(seed), len(tokens)) - 1
                while shared < limit and seed[shared] == tokens[shared]:
                    shared += 1
                if shared == len(tokens) - 1:
                    # Its whole reusable prefix will be seeded, including
                    # duplicate inputs and inputs that are prefixes of seed.
                    ready.append(index)
                else:
                    branches.setdefault((shared, tokens[shared]), []).append(index)
            following.extend((branch, depth + 1) for (depth, _), branch in branches.items())
        batches.append(sorted(batch))
        groups = following
    return batches
