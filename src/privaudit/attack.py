"""What an outsider can recover from a published table with hidden cells.

The attacker sees the visible cells and the row, column and grand totals. Two attacks:

* subtraction (`propagate`): any row or column with exactly one hidden cell gives that cell away
  (total minus the visible cells). Solving one cell can expose the next, so it repeats until stuck.
  Every value it returns is exact, not an estimate.
* interval bounds (`lp_bounds`): for every hidden cell, the smallest and largest value consistent
  with all the totals, found by linear programming. A narrow interval is a near-disclosure even when
  subtraction alone recovers nothing.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import linprog


def propagate(table: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Return an array of recovered values for hidden cells (-1 where the attacker is stuck)."""
    known = np.where(mask, -1, table).astype(np.int64)
    row_totals, col_totals = table.sum(axis=1), table.sum(axis=0)
    unknown = mask.copy()
    progress = True
    while progress:
        progress = False
        for axis, totals in ((0, row_totals), (1, col_totals)):
            for i in range(table.shape[axis]):
                line_unknown = unknown[i] if axis == 0 else unknown[:, i]
                if line_unknown.sum() != 1:
                    continue
                j = int(np.flatnonzero(line_unknown)[0])
                line_known = known[i] if axis == 0 else known[:, i]
                value = totals[i] - line_known[line_known >= 0].sum()
                r, c = (i, j) if axis == 0 else (j, i)
                known[r, c] = value
                unknown[r, c] = False
                progress = True
    return np.where(mask & ~unknown, known, -1)


def lp_bounds(table: np.ndarray, mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Tightest [low, high] for every hidden cell given the totals and non-negative counts."""
    cells = list(zip(*np.nonzero(mask)))
    lows, highs = np.full(table.shape, np.nan), np.full(table.shape, np.nan)
    if not cells:
        return lows, highs
    index = {cell: n for n, cell in enumerate(cells)}
    a_eq, b_eq = [], []
    visible = np.where(mask, 0, table)
    for axis in (0, 1):
        totals = table.sum(axis=1 - axis)
        for i in range(table.shape[axis]):
            members = [index[c] for c in cells if c[axis] == i]
            if not members:
                continue
            row = np.zeros(len(cells))
            row[members] = 1
            a_eq.append(row)
            b_eq.append(totals[i] - (visible[i].sum() if axis == 0 else visible[:, i].sum()))
    a_eq, b_eq = np.array(a_eq), np.array(b_eq)
    for cell, n in index.items():
        objective = np.zeros(len(cells))
        objective[n] = 1
        low = linprog(objective, A_eq=a_eq, b_eq=b_eq, bounds=(0, None), method="highs")
        high = linprog(-objective, A_eq=a_eq, b_eq=b_eq, bounds=(0, None), method="highs")
        lows[cell], highs[cell] = round(low.fun), round(-high.fun)
    return lows, highs
