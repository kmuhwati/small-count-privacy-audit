"""Differentially private counts with the discrete Laplace (two-sided geometric) mechanism.

Adding or removing one person changes exactly one cell of a two-way table by 1, so noise with
scale 1/epsilon on every cell gives epsilon-differential privacy for the whole table. The totals are
then computed from the noisy cells, which keeps the table consistent and costs no extra privacy
(post-processing). Clamping negative counts to zero is also post-processing.
"""
from __future__ import annotations

import numpy as np


def discrete_laplace(shape, epsilon: float, rng: np.random.Generator) -> np.ndarray:
    """Integer noise with P(z) proportional to exp(-epsilon * |z|)."""
    p = 1 - np.exp(-epsilon)
    return rng.geometric(p, size=shape) - rng.geometric(p, size=shape)


def noisy_table(table: np.ndarray, epsilon: float, rng: np.random.Generator) -> np.ndarray:
    return np.maximum(table + discrete_laplace(table.shape, epsilon, rng), 0)


def p_exact(epsilon: float) -> float:
    """Chance a single noisy cell equals the true count, i.e. the best case for an attacker's guess.

    With discrete Laplace noise P(noise = 0) = tanh(epsilon / 2). Unlike subtraction under
    suppression, the attacker can never tell which guesses are the right ones.
    """
    return float(np.tanh(epsilon / 2))
