import { useEffect, useMemo, useState } from "react";
import { complementary, noisyTable, pExact, primary, propagate, rng, sum } from "./privacy.js";

const REPO = "https://github.com/kmuhwati/small-count-privacy-audit";
const AUTHOR = "https://kmuhwati.github.io/";
const MODES = [
  { id: "primary", label: "Suppress small counts", note: "Hide 1 to k−1, publish everything else and the totals." },
  { id: "complementary", label: "Add complementary cells", note: "Also hide cells so no row or column has a single blank." },
  { id: "dp", label: "Differential privacy", note: "Publish every cell with calibrated random noise." },
];
const EPSILONS = [0.1, 0.25, 0.5, 1, 2];
const fmt = (n) => n.toLocaleString("en-US");
const pct = (x) => `${(100 * x).toFixed(x < 0.1 ? 1 : 0)}%`;

function useData() {
  const [state, setState] = useState({ tables: null, findings: null, error: null });
  useEffect(() => {
    const base = import.meta.env.BASE_URL;
    Promise.all([fetch(`${base}tables.json`).then((r) => r.json()), fetch(`${base}findings.json`).then((r) => r.json())])
      .then(([tables, findings]) => setState({ tables, findings, error: null }))
      .catch((error) => setState({ tables: null, findings: null, error }));
  }, []);
  return state;
}

/** The published table for any ordered pair of attributes (stored once per pair, transposed as needed). */
function tableFor(data, rows, cols) {
  const direct = data.tables[`${rows}|${cols}`];
  if (direct) return direct;
  const flipped = data.tables[`${cols}|${rows}`];
  return flipped[0].map((_, c) => flipped.map((row) => row[c]));
}

export default function App() {
  const { tables: data, findings, error } = useData();
  const [rows, setRows] = useState("native_country");
  const [cols, setCols] = useState("income");
  const [k, setK] = useState(11);
  const [mode, setMode] = useState("primary");
  const [epsIndex, setEpsIndex] = useState(3);
  const [seed, setSeed] = useState(1);
  const [showTruth, setShowTruth] = useState(false);
  const [sel, setSel] = useState(null);

  const view = useMemo(() => {
    if (!data) return null;
    const table = tableFor(data, rows, cols);
    const epsilon = EPSILONS[epsIndex];
    const hiddenPrimary = primary(table, k);
    const hidden = mode === "complementary" ? complementary(table, hiddenPrimary) : hiddenPrimary;
    const attack = mode === "dp" ? { values: table.map((r) => r.map(() => -1)), steps: [] } : propagate(table, hidden);
    const noisy = mode === "dp" ? noisyTable(table, epsilon, rng(seed * 7919 + k)) : null;
    return { table, hidden, attack, noisy, epsilon };
  }, [data, rows, cols, k, mode, epsIndex, seed]);

  // Open on the first recovered cell so the attack is visible straight away
  useEffect(() => {
    if (!view) return;
    const first = view.attack.steps[0];
    setSel(first ? { i: first.row, j: first.col } : null);
  }, [rows, cols, k, mode, Boolean(view)]); // eslint-disable-line react-hooks/exhaustive-deps

  if (error) return <div className="app"><p className="pad">Could not load the data: {String(error)}</p></div>;
  if (!data || !view) return <div className="app"><p className="pad muted">Loading census tables…</p></div>;

  const attrs = data.attributes;
  const { table, hidden, attack, noisy, epsilon } = view;
  const rowLabels = attrs[rows].categories;
  const colLabels = attrs[cols].categories;
  const shown = noisy || table;
  const rowTotals = shown.map((r) => sum(r));
  const colTotals = shown[0].map((_, c) => sum(shown.map((r) => r[c])));
  const grand = sum(rowTotals);
  const maxCell = Math.max(1, ...shown.flat());

  const nonzero = table.flat().filter((v) => v > 0).length;
  const hiddenCount = hidden.flat().filter(Boolean).length;
  const steps = attack.steps;
  const exposed = sum(steps.map((s) => s.value));
  const withheld = sum(table.flatMap((r, i) => r.filter((_, j) => hidden[i][j])));
  const dpErrors = noisy ? table.flatMap((r, i) => r.map((v, j) => Math.abs(noisy[i][j] - v))) : [];
  const mae = dpErrors.length ? sum(dpErrors) / dpErrors.length : 0;
  const within2 = dpErrors.length ? dpErrors.filter((e) => e <= 2).length / dpErrors.length : 0;

  const stepAt = (i, j) => steps.find((s) => s.row === i && s.col === j);
  const selStep = sel && stepAt(sel.i, sel.j);
  const inLine = (i, j) => Boolean(selStep) && (selStep.axis === 0 ? i === selStep.row : j === selStep.col);

  const pickRows = (v) => { setRows(v); if (v === cols) setCols(rows); };
  const pickCols = (v) => { setCols(v); if (v === rows) setRows(cols); };

  const cellPanel = (
    <>
      <h3>Selected cell</h3>
      {sel ? (
        <CellDetail
          rowLabel={rowLabels[sel.i]} colLabel={colLabels[sel.j]} truth={table[sel.i][sel.j]}
          noisy={noisy && noisy[sel.i][sel.j]} hidden={hidden[sel.i][sel.j]} step={selStep}
          recovered={attack.values[sel.i][sel.j]} mode={mode} k={k} rowLabels={rowLabels} colLabels={colLabels}
        />
      ) : (
        <p className="hint">Click any cell in the table to inspect it.</p>
      )}
    </>
  );

  const subtitle = mode === "dp"
    ? `Every cell published with noise at ε = ${epsilon}. Totals are sums of the noisy cells.`
    : mode === "complementary"
      ? `Counts of 1 to ${k - 1} hidden, plus extra cells so no line has a single blank. Hidden cells all show *.`
      : `Counts of 1 to ${k - 1} hidden, totals published. Red cells are ones the attacker worked out.`;

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="mark" aria-hidden="true" />
          <span className="name">Small-count audit</span>
          <span className="crumb">UCI Adult census · {fmt(data.people)} people</span>
        </div>
        <nav>
          <a href={REPO}>Method and code</a>
          <a href={AUTHOR}>Kumbirai Muhwati</a>
        </nav>
      </header>

      {findings && (
        <div className="banner">
          <strong>Across all {findings.tables} two-way tables,</strong> the 1-to-10 rule hides {fmt(findings.suppressed_cells)} cells
          and plain subtraction recovers <strong className="leak">{fmt(findings.recovered_cells)} of them exactly</strong>, in{" "}
          {findings.tables_with_recovery} tables. Pick any table to see where.
        </div>
      )}

      <div className="layout">
        <main className="main">
          <div className="titlebar">
            <h1>{attrs[rows].label} <span className="x">×</span> {attrs[cols].label}</h1>
            <p>{subtitle}</p>
          </div>

          <dl className="metrics">
            {mode === "dp" ? (
              <>
                <Metric label="Mean error per cell" value={mae.toFixed(2)} unit="people" />
                <Metric label="Cells within ±2" value={pct(within2)} />
                <Metric label="Attacker's exact-guess chance" value={pct(pExact(epsilon))} />
                <Metric label="Cells known for certain" value="0" tone="ok" />
              </>
            ) : (
              <>
                <Metric label="Hidden cells" value={fmt(hiddenCount)} unit={`${pct(nonzero ? hiddenCount / nonzero : 0)} of non-empty`} />
                <Metric label="Recovered exactly" value={fmt(steps.length)} tone={steps.length ? "leak" : "ok"} />
                <Metric label="People in recovered cells" value={fmt(exposed)} tone={exposed ? "leak" : "ok"} />
                <Metric label="Counts withheld from readers" value={fmt(withheld)} unit="people" />
              </>
            )}
          </dl>

          <section className="matrix" aria-label="Published table">
            <div className="matrix-head">
              <span className="caption">Published table</span>
              <span className="key">
                {mode === "dp" ? (
                  <><i className="sw scale" /> darker = larger count</>
                ) : (
                  <><i className="sw hatch" /> hidden <i className="sw leak" /> recovered <i className="sw line" /> line used</>
                )}
              </span>
            </div>
            <div className="scroll">
              <table className="grid">
                <thead>
                  <tr>
                    <th scope="col" className="corner">{attrs[rows].label}</th>
                    {colLabels.map((c, j) => <th scope="col" key={c} className={selStep && selStep.axis === 1 && j === selStep.col ? "hl" : ""}>{c}</th>)}
                    <th scope="col" className="total">Total</th>
                  </tr>
                </thead>
                <tbody>
                  {table.map((row, i) => (
                    <tr key={rowLabels[i]}>
                      <th scope="row" className={selStep && selStep.axis === 0 && i === selStep.row ? "hl" : ""}>{rowLabels[i]}</th>
                      {row.map((v, j) => {
                        const value = noisy ? noisy[i][j] : v;
                        const isSel = sel && sel.i === i && sel.j === j;
                        const state = noisy ? "noisy" : attack.values[i][j] >= 0 ? "leak" : hidden[i][j] ? "hidden" : "plain";
                        const text = state === "hidden" ? (mode === "complementary" ? "*" : `<${k}`) : fmt(value);
                        const tint = state === "plain" || state === "noisy" ? Math.log1p(Math.max(0, value)) / Math.log1p(maxCell) : 0;
                        return (
                          <td key={j} className={`c ${state}${isSel ? " sel" : ""}${inLine(i, j) ? " line" : ""}`} style={{ "--t": tint.toFixed(3) }}>
                            <button type="button" onClick={() => setSel({ i, j })} aria-label={`${rowLabels[i]}, ${colLabels[j]}: ${text}`}>
                              {text}
                              {noisy && showTruth && <small>{fmt(v)}</small>}
                            </button>
                          </td>
                        );
                      })}
                      <td className={`total${selStep && selStep.axis === 0 && i === selStep.row ? " line" : ""}`}>{fmt(rowTotals[i])}</td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr>
                    <th scope="row">Total</th>
                    {colTotals.map((t, j) => <td key={j} className={`total${selStep && selStep.axis === 1 && j === selStep.col ? " line" : ""}`}>{fmt(t)}</td>)}
                    <td className="total">{fmt(grand)}</td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </section>

          <section className="cell-panel cell-inline">{cellPanel}</section>

          {mode !== "dp" && steps.length > 0 && (
            <section className="log">
              <h2>Attack log <span className="count">{steps.length} {steps.length === 1 ? "cell" : "cells"}</span></h2>
              <div className="scroll">
                <table>
                  <thead>
                    <tr><th>#</th><th>Line used</th><th className="num">Total</th><th className="num">Visible</th><th className="num">Recovered</th><th>Cell</th></tr>
                  </thead>
                  <tbody>
                    {steps.map((s, n) => (
                      <tr key={`${s.row}-${s.col}`} className={sel && sel.i === s.row && sel.j === s.col ? "on" : ""} onClick={() => setSel({ i: s.row, j: s.col })}>
                        <td className="muted">{n + 1}</td>
                        <td>{s.axis === 0 ? rowLabels[s.row] : colLabels[s.col]} <span className="muted">{s.axis === 0 ? "row" : "column"}</span></td>
                        <td className="num">{fmt(s.total)}</td>
                        <td className="num">− {fmt(s.others)}</td>
                        <td className="num leak">= {s.value}</td>
                        <td className="muted">{rowLabels[s.row]} · {colLabels[s.col]}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          <section className="notes">
            <div>
              <h2>Why hiding small counts fails</h2>
              <p>
                A row with one hidden cell gives it away: the total minus the visible cells is the hidden count. Hiding
                extra cells stops that, but linear programming can still pin many hidden cells to a narrow range, and
                honest readers lose more of the table.
              </p>
            </div>
            <div>
              <h2>Why differential privacy holds</h2>
              <p>
                Noise goes on every count. The attacker can still subtract, but they recover noise rather than people,
                and they cannot tell which guesses happen to be right. The budget ε states the trade-off between
                accuracy and privacy, and it can be audited.
              </p>
            </div>
          </section>
        </main>

        <aside className="inspector" aria-label="Settings and cell details">
          <section className="cfg">
            <h3>Breakdown</h3>
            <label className="field">
              <span>Rows</span>
              <select value={rows} onChange={(e) => pickRows(e.target.value)}>
                {Object.entries(attrs).map(([key, a]) => <option key={key} value={key}>{a.label}</option>)}
              </select>
            </label>
            <label className="field">
              <span>Columns</span>
              <select value={cols} onChange={(e) => pickCols(e.target.value)}>
                {Object.entries(attrs).map(([key, a]) => <option key={key} value={key}>{a.label}</option>)}
              </select>
            </label>
          </section>

          <section className="cfg">
            <h3>Protection</h3>
            <div className="options" role="radiogroup" aria-label="Protection method">
              {MODES.map((m) => (
                <button key={m.id} type="button" role="radio" aria-checked={mode === m.id} className={mode === m.id ? "on" : ""} onClick={() => setMode(m.id)}>
                  <span className="opt-label">{m.label}</span>
                  <span className="opt-note">{m.note}</span>
                </button>
              ))}
            </div>
            {mode === "dp" ? (
              <>
                <label className="slider">
                  <span>Privacy budget <b>ε = {epsilon}</b></span>
                  <input type="range" min="0" max={EPSILONS.length - 1} value={epsIndex} onChange={(e) => setEpsIndex(Number(e.target.value))} />
                  <span className="ends"><span>more private</span><span>more accurate</span></span>
                </label>
                <div className="row-actions">
                  <button type="button" className="btn" onClick={() => setSeed((s) => s + 1)}>New noise draw</button>
                  <label className="check"><input type="checkbox" checked={showTruth} onChange={(e) => setShowTruth(e.target.checked)} /> Show true counts</label>
                </div>
              </>
            ) : (
              <label className="slider">
                <span>Hide counts below <b>k = {k}</b></span>
                <input type="range" min="2" max="20" value={k} onChange={(e) => setK(Number(e.target.value))} />
                <span className="ends"><span>2</span><span>20</span></span>
              </label>
            )}
          </section>

          <section className="cell-panel">{cellPanel}</section>

          {findings && (
            <section>
              <h3>All {findings.tables} tables at k = {findings.k}</h3>
              <dl className="kv">
                <div><dt>Cells hidden</dt><dd>{fmt(findings.suppressed_cells)}</dd></div>
                <div><dt>Recovered exactly</dt><dd className="leak">{fmt(findings.recovered_cells)} ({pct(findings.recovered_share)})</dd></div>
                <div><dt>Tables that leak</dt><dd>{findings.tables_with_recovery}</dd></div>
                <div><dt>People in recovered cells</dt><dd>{fmt(findings.people_in_recovered_cells)}</dd></div>
                <div><dt>Narrow after complementary</dt><dd>{fmt(findings.lp_small_cells_still_narrow)}</dd></div>
              </dl>
            </section>
          )}
        </aside>
      </div>

      <footer className="foot">
        Data: UCI Adult (1994 US Census extract). Everything runs in your browser and nothing is sent anywhere.
        Method, results and tests on <a href={REPO}>GitHub</a>.
      </footer>
    </div>
  );
}

function Metric({ label, value, unit, tone }) {
  return (
    <div className={`metric ${tone || ""}`}>
      <dt>{label}</dt>
      <dd>{value}{unit && <span>{unit}</span>}</dd>
    </div>
  );
}

function CellDetail({ rowLabel, colLabel, truth, noisy, hidden, step, recovered, mode, k, rowLabels, colLabels }) {
  const where = <p className="where">{rowLabel} <span>·</span> {colLabel}</p>;
  if (mode === "dp") {
    return (
      <>
        {where}
        <span className="pill neutral">Noisy</span>
        <dl className="kv">
          <div><dt>Published</dt><dd>{fmt(noisy)}</dd></div>
          <div><dt>True count</dt><dd>{fmt(truth)}</dd></div>
          <div><dt>Error</dt><dd>{noisy - truth >= 0 ? "+" : "−"}{Math.abs(noisy - truth)}</dd></div>
        </dl>
        <p className="hint">The attacker sees only the published number and cannot tell how far off it is.</p>
      </>
    );
  }
  if (recovered >= 0 && step) {
    const line = step.axis === 0 ? `${rowLabels[step.row]} row` : `${colLabels[step.col]} column`;
    return (
      <>
        {where}
        <span className="pill leak">Recovered</span>
        <div className="calc" role="group" aria-label="How the attacker worked it out">
          <span>{line} total</span><span>{fmt(step.total)}</span>
          <span>visible cells</span><span>− {fmt(step.others)}</span>
          <span className="res">hidden count</span><span className="res">= {step.value}</span>
        </div>
        <p className="hint">This was the only blank left in its {step.axis === 0 ? "row" : "column"}, so the published total gives it away.</p>
      </>
    );
  }
  if (hidden) {
    return (
      <>
        {where}
        <span className="pill hidden">Hidden</span>
        <dl className="kv">
          <div><dt>Published</dt><dd>{mode === "complementary" ? "*" : `<${k}`}</dd></div>
          <div><dt>True count</dt><dd>{fmt(truth)}</dd></div>
        </dl>
        <p className="hint">Its row and its column each still have two or more blanks, so subtraction alone cannot solve it.</p>
      </>
    );
  }
  return (
    <>
      {where}
      <span className="pill neutral">Visible</span>
      <dl className="kv">
        <div><dt>Published</dt><dd>{fmt(truth)}</dd></div>
      </dl>
      <p className="hint">{truth === 0 ? "Zeros are published, as in most real rules." : `At least ${k}, so the rule leaves it alone.`}</p>
    </>
  );
}
