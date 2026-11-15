"""Small-count suppression, as health and statistics agencies publish it.

A report shows a two-way count table with its row totals, column totals and grand total. Any cell
from 1 to k-1 is hidden (CMS, for example, hides counts of 1 to 10, i.e. k = 11). Zeros are shown.

Primary suppression hides only those small cells. Complementary suppression also hides extra cells,
so that no row or column of the table has exactly one hidden cell, which is the classic fix for the
subtraction attack in attack.py.
"""
from __future__ import annotations

import numpy as np


def primary(table: np.ndarray, k: int) -> np.ndarray:
    """Boolean mask of cells hidden by the small-count rule: 1 <= count < k."""
    return (table >= 1) & (table < k)


def complementary(table: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Add the fewest, smallest extra cells so every row and column has 0 or >= 2 hidden cells.

    Greedy: for each line (row or column) with a single hidden cell, also hide that line's smallest
    visible cell (zeros count, since hiding a zero costs no information). Repeat until stable, because
    hiding a cell can leave its other line with a single hidden cell.
    """
    mask = mask.copy()
    while True:
        changed = False
        for axis in (0, 1):
            lines = mask.T if axis else mask
            values = table.T if axis else table
            for i in range(lines.shape[0]):
                if lines[i].sum() != 1:
                    continue
                visible = np.flatnonzero(~lines[i])
                if visible.size == 0:
                    continue
                j = visible[np.argmin(values[i, visible])]
                if axis:
                    mask[j, i] = True
                else:
                    mask[i, j] = True
                changed = True
        if not changed:
            return mask
