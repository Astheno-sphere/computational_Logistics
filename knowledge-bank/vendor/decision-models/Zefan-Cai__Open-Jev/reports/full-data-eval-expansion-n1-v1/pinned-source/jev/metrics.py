"""Decision metrics and calibration, with no training-library dependency.

Binary (Noul) rows use [P(false), P(true)]. Rows may have different class
counts. Calibration must be fitted on the calibration split, never test data.
"""

import math
from numbers import Integral
from typing import Sequence


Target = int | Sequence[float]


def sigmoid(value: float) -> float:
    """Numerically stable binary probability."""
    if math.isnan(value):
        raise ValueError("sigmoid input must not be NaN")
    if value >= 0:
        return 1.0 / (1.0 + math.exp(-value))
    exponential = math.exp(value)
    return exponential / (1.0 + exponential)


def softmax(logits: Sequence[float], temperature: float = 1.0) -> list[float]:
    """Stable softmax; -inf is allowed for masked classes."""
    if not math.isfinite(temperature) or temperature <= 0:
        raise ValueError("temperature must be finite and positive")
    if not logits or any(math.isnan(x) or x == math.inf for x in logits):
        raise ValueError("logits must be nonempty and contain no NaN or +inf")
    maximum = max(logits)
    if maximum == -math.inf:
        raise ValueError("at least one logit must be finite")
    weights = [math.exp((value - maximum) / temperature) for value in logits]
    total = sum(weights)
    return [weight / total for weight in weights]


def _distribution(values: Sequence[float]) -> list[float]:
    result = [float(value) for value in values]
    if not result or any(not math.isfinite(x) or x < 0 for x in result):
        raise ValueError("probabilities must be nonempty, finite and nonnegative")
    total = sum(result)
    if not math.isclose(total, 1.0, rel_tol=1e-6, abs_tol=1e-6):
        raise ValueError("probabilities must sum to one")
    return [value / total for value in result]


def _target_distribution(target: Target, count: int) -> list[float]:
    if isinstance(target, Integral):
        if target < 0 or target >= count:
            raise ValueError("target class is outside the candidate set")
        return [float(index == target) for index in range(count)]
    result = _distribution(target)
    if len(result) != count:
        raise ValueError("target and probability class counts differ")
    return result


def _confidence_distribution(probs: Sequence[float]) -> list[float]:
    # Match the official adapter's handling of unnormalized and zero-total input.
    values = [float(value) for value in probs]
    if not values or any(not math.isfinite(x) or x < 0 for x in values):
        raise ValueError("confidence inputs must be finite and nonnegative")
    total = sum(values)
    return [value / total for value in values] if total else [1.0 / len(values)] * len(values)


def choice_confidence(probs: Sequence[float]) -> float:
    """Official system-one-adapter formula, not calibrated correctness.

    Reference commit: adffc2eab300a4fa3c0e92252d4ffd6ceaa53700.
    """
    probabilities = _confidence_distribution(probs)
    if len(probabilities) == 1:
        return 1.0
    uniform = 1.0 / len(probabilities)
    return (max(probabilities) - uniform) / (1.0 - uniform)


def score_confidence(probs: Sequence[float]) -> float:
    """Official adapter's concentration around the first modal ordinal level."""
    probabilities = _confidence_distribution(probs)
    count = len(probabilities)
    if count == 1:
        return 1.0
    mode = max(range(count), key=probabilities.__getitem__)
    distance = sum(prob * abs(index - mode) for index, prob in enumerate(probabilities))
    center = (count - 1) / 2
    uniform_deviation = sum(abs(index - center) for index in range(count)) / count
    return max(0.0, 1.0 - distance / uniform_deviation)


def evaluate_probabilities(
    targets: Sequence[Target],
    probs: Sequence[Sequence[float]],
    *,
    n_bins: int = 15,
    thresholds: Sequence[float] = (0.5, 0.7, 0.8, 0.9, 0.95, 0.99),
) -> dict:
    """Evaluate hard labels and soft target distributions without fake labels.

    `accuracy` uses only integer or exactly one-hot targets; it is None when
    none exist. `expected_accuracy` uses target mass at the predicted class.
    `brier` is sum-of-squares distance to the target distribution. The separate
    `expected_brier` is expected one-hot Brier loss under soft target outcomes.
    NLL floors probabilities at 1e-15. Multiclass ECE is top-label ECE using
    equal-width bins and expected correctness for soft targets. Coverage uses
    max probability, not either TypeSafe confidence formula.
    """
    if len(targets) != len(probs) or not targets:
        raise ValueError("targets and probabilities must have equal nonzero length")
    if not isinstance(n_bins, Integral) or n_bins <= 0:
        raise ValueError("n_bins must be a positive integer")
    if any(not math.isfinite(t) or not 0 <= t <= 1 for t in thresholds):
        raise ValueError("coverage thresholds must be in [0, 1]")
    bins = [[0, 0.0, 0.0] for _ in range(n_bins)]
    observations = []
    nll = brier = expected_brier = 0.0
    for target, row in zip(targets, probs):
        probability = _distribution(row)
        truth = _target_distribution(target, len(probability))
        prediction = max(range(len(probability)), key=probability.__getitem__)
        confidence = probability[prediction]
        expected_correct = truth[prediction]
        hard = max(truth) == 1.0
        observations.append((confidence, expected_correct, hard))
        nll -= sum(q * math.log(max(p, 1e-15)) for q, p in zip(truth, probability))
        squared_distance = sum((p - q) ** 2 for p, q in zip(probability, truth))
        brier += squared_distance
        expected_brier += squared_distance + 1.0 - sum(q * q for q in truth)
        bucket = bins[min(int(confidence * n_bins), n_bins - 1)]
        bucket[0] += 1
        bucket[1] += confidence
        bucket[2] += expected_correct

    def summarize(rows: list) -> dict:
        selected = len(rows)
        hard_rows = [correct for _, correct, hard in rows if hard]
        expected_accuracy = sum(row[1] for row in rows) / selected if selected else None
        return {
            "selected": selected,
            "coverage": selected / len(observations),
            "accuracy": sum(hard_rows) / len(hard_rows) if hard_rows else None,
            "expected_accuracy": expected_accuracy,
            "expected_risk": 1.0 - expected_accuracy if selected else None,
        }

    overall = summarize(observations)
    return {
        "count": len(observations),
        "hard_count": sum(row[2] for row in observations),
        "accuracy": overall["accuracy"],
        "expected_accuracy": overall["expected_accuracy"],
        "nll": nll / len(observations),
        "brier": brier / len(observations),
        "expected_brier": expected_brier / len(observations),
        "multiclass_ece": sum(abs(confidence - correct) for _, confidence, correct in bins) / len(observations),
        "ece_bins": n_bins,
        "coverage": [
            {"threshold": threshold, **summarize([row for row in observations if row[0] >= threshold])}
            for threshold in thresholds
        ],
    }


def fit_temperature(
    logits: Sequence[Sequence[float]],
    targets: Sequence[Target],
    *,
    min_temperature: float = 0.05,
    max_temperature: float = 20.0,
    grid_size: int = 25,
    refine_steps: int = 24,
) -> float:
    """Fit one positive temperature by calibration-set cross entropy.

    Pure Python log-spaced grid followed by golden-section refinement. Inputs
    are validated once, and target-weighted logits are precomputed. Fit once
    on the calibration split, freeze the returned float, and use it on test.
    """
    if len(logits) != len(targets) or not logits:
        raise ValueError("logits and targets must have equal nonzero length")
    if not (math.isfinite(min_temperature) and math.isfinite(max_temperature)
            and 0 < min_temperature < max_temperature):
        raise ValueError("temperature bounds must be finite, positive and ordered")
    if not isinstance(grid_size, Integral) or grid_size < 3 or not isinstance(refine_steps, Integral) or refine_steps < 0:
        raise ValueError("grid_size must be >= 3 and refine_steps must be >= 0")
    prepared = []
    for row, target in zip(logits, targets):
        if not row or any(not math.isfinite(value) for value in row):
            raise ValueError("calibration logits must be nonempty and finite")
        truth = _target_distribution(target, len(row))
        maximum = max(row)
        shifted = [value - maximum for value in row]
        prepared.append((shifted, sum(q * value for q, value in zip(truth, shifted))))

    def loss(log_temperature: float) -> float:
        inverse = math.exp(-log_temperature)
        return sum(
            math.log(sum(math.exp(value * inverse) for value in row)) - expected * inverse
            for row, expected in prepared
        ) / len(prepared)

    lower, upper = math.log(min_temperature), math.log(max_temperature)
    grid = [lower + index * (upper - lower) / (grid_size - 1) for index in range(grid_size)]
    if lower <= 0 <= upper:
        grid = sorted(set(grid + [0.0]))
    losses = [loss(point) for point in grid]
    best = min(range(len(grid)), key=lambda index: (losses[index], abs(grid[index])))
    candidates = [(losses[best], grid[best])]
    left, right = grid[max(0, best - 1)], grid[min(len(grid) - 1, best + 1)]
    ratio = (math.sqrt(5) - 1) / 2
    first, second = right - ratio * (right - left), left + ratio * (right - left)
    first_loss, second_loss = loss(first), loss(second)
    for _ in range(refine_steps):
        if first_loss < second_loss:
            right, second, second_loss = second, first, first_loss
            first = right - ratio * (right - left)
            first_loss = loss(first)
        else:
            left, first, first_loss = first, second, second_loss
            second = left + ratio * (right - left)
            second_loss = loss(second)
    candidates.extend([(first_loss, first), (second_loss, second)])
    return math.exp(min(candidates, key=lambda candidate: (candidate[0], abs(candidate[1])))[1])
