"""Tests on small hand-made tables with known answers (no download needed)."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from privaudit import attack, dp, suppression  # noqa: E402

# Rows: three clinics. Columns: three diagnoses. Cells of 1-10 are hidden at k = 11.
TABLE = np.array([[40, 3, 25],
                  [30, 50, 2],
                  [12, 8, 60]])


def test_primary_hides_one_to_k_minus_one_and_shows_zeros():
    t = np.array([[0, 1, 10, 11]])
    assert suppression.primary(t, 11).tolist() == [[False, True, True, False]]


def test_subtraction_recovers_lone_hidden_cells_exactly():
    hidden = suppression.primary(TABLE, 11)            # 3, 2 and 8 are hidden
    recovered = attack.propagate(TABLE, hidden)
    # Row 0 and row 1 each hide one cell, so totals give them away; that leaves column 1 with one unknown
    assert recovered[0, 1] == 3 and recovered[1, 2] == 2 and recovered[2, 1] == 8
    assert (recovered[~hidden] == -1).all()


def test_attack_is_stuck_when_two_cells_share_every_line():
    t = np.array([[5, 5, 30], [5, 5, 30], [30, 30, 30]])
    hidden = suppression.primary(t, 11)                # a 2x2 block of 5s: every line has two unknowns
    assert (attack.propagate(t, hidden) == -1).all()


def test_complementary_suppression_blocks_subtraction():
    hidden = suppression.complementary(TABLE, suppression.primary(TABLE, 11))
    for axis in (0, 1):
        assert set(hidden.sum(axis=axis).tolist()) <= {0, 2, 3}
    assert (attack.propagate(TABLE, hidden) == -1).all()


def test_lp_bounds_contain_the_truth_and_pin_forced_cells():
    t = np.array([[5, 5, 30], [5, 5, 30], [30, 30, 30]])
    hidden = suppression.primary(t, 11)
    low, high = attack.lp_bounds(t, hidden)
    assert (low[hidden] <= t[hidden]).all() and (t[hidden] <= high[hidden]).all()
    assert high[0, 0] == 10                            # each 5 could be anything from 0 to 10


def test_discrete_laplace_is_centred_and_matches_p_exact():
    rng = np.random.default_rng(0)
    noise = dp.discrete_laplace(200_000, 1.0, rng)
    assert abs(noise.mean()) < 0.02
    assert abs((noise == 0).mean() - dp.p_exact(1.0)) < 0.01


def test_noisy_table_is_non_negative_and_integer():
    out = dp.noisy_table(TABLE, 0.1, np.random.default_rng(1))
    assert out.dtype.kind == "i" and (out >= 0).all()
