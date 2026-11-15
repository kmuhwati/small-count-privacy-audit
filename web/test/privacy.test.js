// Checks the dashboard's JavaScript against the Python audit (fixtures written by scripts/run_audit.py).
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { complementary, noisyTable, pExact, primary, propagate, rng } from "../src/privacy.js";

const fixtures = JSON.parse(readFileSync(new URL("./fixtures.json", import.meta.url), "utf8"));
const asInts = (m) => m.map((row) => row.map(Number));

for (const f of fixtures) {
  test(`matches Python on ${f.name}`, () => {
    const p = primary(f.table, f.k);
    assert.deepEqual(asInts(p), f.primary);
    assert.deepEqual(asInts(complementary(f.table, p)), f.complementary);
    assert.deepEqual(propagate(f.table, p).values, f.recovered);
  });
}

test("every recovered value is the true count", () => {
  for (const f of fixtures) {
    const { values } = propagate(f.table, primary(f.table, f.k));
    values.forEach((row, r) => row.forEach((v, c) => v >= 0 && assert.equal(v, f.table[r][c])));
  }
});

test("discrete Laplace noise is centred and P(0) matches tanh(eps/2)", () => {
  const random = rng(7);
  const table = [Array(100_000).fill(1000)];
  const noise = noisyTable(table, 1, random)[0].map((v) => v - 1000);
  const mean = noise.reduce((a, b) => a + b, 0) / noise.length;
  assert.ok(Math.abs(mean) < 0.03, `mean ${mean}`);
  const zeros = noise.filter((v) => v === 0).length / noise.length;
  assert.ok(Math.abs(zeros - pExact(1)) < 0.01, `P(0) ${zeros}`);
});
