#!/usr/bin/env python3
"""Survey sample size from the two hypotheses, reported with the minimum detectable effect.

H2 (information): three randomised arms in wave 1; the smallest effect worth detecting is a difference of
0.20 standard deviations in stated acceptance between an information arm and control (two-sided,
alpha 0.05, power 0.80; two comparisons, Bonferroni alpha 0.025).
H1 (persistence): within-person change between waves; paired test on the same respondents, detecting
0.15 standard deviations of change, with wave-to-wave attrition of 35%.
Kristiansund needs the larger of the two; Molde carries the acceptance block only and is sized for H2
at half the Kristiansund sample, which detects about 0.28 SD.

    python docs/proposal/power.py
"""
from math import ceil, sqrt

from scipy.stats import norm


def z(alpha, power):
    return norm.ppf(1 - alpha / 2) + norm.ppf(power)


def main():
    per_arm = ceil(2 * (z(0.025, 0.80) / 0.20) ** 2)          # two-sample, standardised difference
    h2 = 3 * per_arm
    pairs = ceil((z(0.05, 0.80) / 0.15) ** 2)                 # paired, standardised change
    h1 = ceil(pairs / (1 - 0.35))
    n_k = max(h2, h1)
    n_m = ceil(n_k / 2)
    mde_m = z(0.025, 0.80) * sqrt(2 / (n_m / 3))
    print(f"H2: {per_arm} per arm, {h2} in wave 1 · H1: {pairs} completers, {h1} invited at 35% attrition")
    print(f"Kristiansund wave 1: {n_k} · Molde: {n_m} (detects {mde_m:.2f} SD between arms)")


if __name__ == "__main__":
    main()
