// JavaScript port of src/privaudit (suppression.py, attack.py, dp.py). It must give the same answers
// as the Python audit; test/privacy.test.js checks it against fixtures that the audit writes.

/** Cells hidden by the small-count rule: 1 <= count < k. */
export function primary(table, k) {
  return table.map((row) => row.map((v) => v >= 1 && v < k));
}

/**
 * Hide the smallest extra cells until no row or column has exactly one hidden cell.
 * Same order and tie-breaking as suppression.complementary (rows, then columns, first minimum wins).
 */
export function complementary(table, mask) {
  const m = mask.map((row) => [...row]);
  const nr = table.length;
  const nc = table[0].length;
  for (;;) {
    let changed = false;
    for (const axis of [0, 1]) {
      const lines = axis === 0 ? nr : nc;
      const width = axis === 0 ? nc : nr;
      for (let i = 0; i < lines; i++) {
        const at = (j) => (axis === 0 ? [i, j] : [j, i]);
        let hidden = 0;
        for (let j = 0; j < width; j++) {
          const [r, c] = at(j);
          if (m[r][c]) hidden++;
        }
        if (hidden !== 1) continue;
        let best = -1;
        for (let j = 0; j < width; j++) {
          const [r, c] = at(j);
          if (m[r][c]) continue;
          if (best === -1) best = j;
          else {
            const [br, bc] = at(best);
            if (table[r][c] < table[br][bc]) best = j;
          }
        }
        if (best === -1) continue;
        const [r, c] = at(best);
        m[r][c] = true;
        changed = true;
      }
    }
    if (!changed) return m;
  }
}

/**
 * The subtraction attack. Returns { values, steps }: values[r][c] is the recovered count (or -1),
 * and steps lists, in order, how each cell was worked out (which total minus which visible cells).
 */
export function propagate(table, mask) {
  const nr = table.length;
  const nc = table[0].length;
  const rowTotals = table.map((row) => row.reduce((a, b) => a + b, 0));
  const colTotals = table[0].map((_, c) => table.reduce((a, row) => a + row[c], 0));
  const known = table.map((row, r) => row.map((v, c) => (mask[r][c] ? -1 : v)));
  const unknown = mask.map((row) => [...row]);
  const steps = [];
  let progress = true;
  while (progress) {
    progress = false;
    for (const axis of [0, 1]) {
      const lines = axis === 0 ? nr : nc;
      const width = axis === 0 ? nc : nr;
      for (let i = 0; i < lines; i++) {
        const at = (j) => (axis === 0 ? [i, j] : [j, i]);
        let count = 0;
        let lone = -1;
        for (let j = 0; j < width; j++) {
          const [r, c] = at(j);
          if (unknown[r][c]) {
            count++;
            lone = j;
          }
        }
        if (count !== 1) continue;
        let others = 0;
        for (let j = 0; j < width; j++) {
          const [r, c] = at(j);
          if (known[r][c] >= 0) others += known[r][c];
        }
        const total = axis === 0 ? rowTotals[i] : colTotals[i];
        const [r, c] = at(lone);
        known[r][c] = total - others;
        unknown[r][c] = false;
        steps.push({ row: r, col: c, axis, line: i, total, others, value: total - others });
        progress = true;
      }
    }
  }
  const values = table.map((row, r) => row.map((_, c) => (mask[r][c] && !unknown[r][c] ? known[r][c] : -1)));
  return { values, steps };
}

/** Small seeded PRNG (mulberry32), so a "noise draw" can be repeated. */
export function rng(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function geometric(p, random) {
  // Number of trials until the first success, like numpy's Generator.geometric
  return Math.max(1, Math.ceil(Math.log(1 - random()) / Math.log(1 - p)));
}

/** Discrete Laplace noise on every cell (epsilon-DP for the whole table), clamped at zero. */
export function noisyTable(table, epsilon, random) {
  const p = 1 - Math.exp(-epsilon);
  return table.map((row) => row.map((v) => Math.max(0, v + geometric(p, random) - geometric(p, random))));
}

/** Chance a noisy cell equals the true count: tanh(epsilon / 2). */
export function pExact(epsilon) {
  return Math.tanh(epsilon / 2);
}

export const sum = (xs) => xs.reduce((a, b) => a + b, 0);
