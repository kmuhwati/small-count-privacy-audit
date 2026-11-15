"""Run the audit over every two-way table and write results, figures and the dashboard's data."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from . import attack, data, dp, plotstyle, suppression

ROOT = data.ROOT
REPORTS, FIGURES, TABLES = ROOT / "reports", ROOT / "reports" / "figures", ROOT / "reports" / "tables"
WEB_DATA = ROOT / "web" / "public" / "tables.json"
FIXTURES = ROOT / "web" / "test" / "fixtures.json"

K = 11                           # CMS-style rule: counts of 1 to 10 are hidden
K_SWEEP = [3, 5, 11, 20]
EPSILONS = [0.1, 0.25, 0.5, 1.0, 2.0]
DP_REPEATS = 25
SEED = 11


def table_audit(table: np.ndarray, k: int, with_lp: bool = True) -> dict:
    nonzero = int((table > 0).sum())
    hidden = suppression.primary(table, k)
    recovered = attack.propagate(table, hidden)
    assert np.array_equal(recovered[recovered >= 0], table[recovered >= 0]), "subtraction must be exact"
    comp = suppression.complementary(table, hidden)
    out = {
        "cells": int(table.size), "nonzero_cells": nonzero, "people": int(table.sum()),
        "suppressed": int(hidden.sum()), "recovered": int((recovered >= 0).sum()),
        "people_in_recovered": int(table[recovered >= 0].sum()),
        "comp_hidden": int(comp.sum()), "comp_recovered": int((attack.propagate(table, comp) >= 0).sum()),
        "comp_people_hidden": int(table[comp].sum()),
    }
    if with_lp and comp.any():
        low, high = attack.lp_bounds(table, comp)
        width = (high - low)[hidden]          # how tightly the originally small cells are pinned
        out["lp_width_median"] = float(np.median(width))
        out["lp_within_small_range"] = int((width < k - 1).sum())
    return out


def run() -> dict:
    plotstyle.apply()
    for d in (FIGURES, TABLES, WEB_DATA.parent, FIXTURES.parent):
        d.mkdir(parents=True, exist_ok=True)
    people = data.load_people()

    rows, web_tables = [], {}
    for a, b in data.all_pairs():
        table, ra, cb = data.crosstab(people, a, b)
        rows.append({"rows": a, "cols": b, **table_audit(table, K)})
        web_tables[f"{a}|{b}"] = table.tolist()
    per_table = pd.DataFrame(rows)
    per_table["recovered_share"] = per_table.recovered / per_table.suppressed.replace(0, np.nan)
    per_table.sort_values("recovered", ascending=False).to_csv(TABLES / "per_table_k11.csv", index=False)

    sweep = []
    for k in K_SWEEP:
        s = r = 0
        for a, b in data.all_pairs():
            t, *_ = data.crosstab(people, a, b)
            m = suppression.primary(t, k)
            s += int(m.sum())
            r += int((attack.propagate(t, m) >= 0).sum())
        sweep.append({"k": k, "suppressed": s, "recovered": r, "recovered_share": r / s if s else 0.0})
    sweep = pd.DataFrame(sweep)
    sweep.to_csv(TABLES / "k_sweep.csv", index=False)

    rng = np.random.default_rng(SEED)
    dp_rows = []
    for eps in EPSILONS:
        abs_err, rel_err_big, small_within_2 = [], [], []
        for a, b in data.all_pairs():
            t, *_ = data.crosstab(people, a, b)
            small, big = (t >= 1) & (t < K), t >= K
            for _ in range(DP_REPEATS):
                noisy = dp.noisy_table(t, eps, rng)
                err = np.abs(noisy - t)
                abs_err.append(err.ravel())
                rel_err_big.append((err[big] / t[big]).ravel())
                small_within_2.append((err[small] <= 2).ravel())
        abs_err, rel_err_big = np.concatenate(abs_err), np.concatenate(rel_err_big)
        dp_rows.append({"epsilon": eps, "mean_abs_error": float(abs_err.mean()),
                        "p95_abs_error": float(np.quantile(abs_err, 0.95)),
                        "median_rel_error_cells_ge_k": float(np.median(rel_err_big)),
                        "small_cells_within_2": float(np.concatenate(small_within_2).mean()),
                        "p_attacker_guess_exact": dp.p_exact(eps)})
    dp_df = pd.DataFrame(dp_rows)
    dp_df.to_csv(TABLES / "dp_utility.csv", index=False)

    totals = per_table[["cells", "nonzero_cells", "suppressed", "recovered", "people_in_recovered",
                        "comp_hidden", "comp_recovered", "comp_people_hidden"]].sum()
    lp = per_table.dropna(subset=["lp_width_median"])
    metrics = {
        "dataset": "UCI Adult (1994 US Census extract), train + test",
        "people": int(len(people)), "tables": int(len(per_table)), "k": K,
        "cells": int(totals.cells), "nonzero_cells": int(totals.nonzero_cells),
        "suppressed_cells": int(totals.suppressed), "recovered_cells": int(totals.recovered),
        "recovered_share": float(totals.recovered / totals.suppressed),
        "tables_with_recovery": int((per_table.recovered > 0).sum()),
        "people_in_recovered_cells": int(totals.people_in_recovered),
        "complementary_hidden_cells": int(totals.comp_hidden),
        "complementary_extra_cells": int(totals.comp_hidden - totals.suppressed),
        "complementary_recovered_cells": int(totals.comp_recovered),
        "hidden_share_primary": float(totals.suppressed / totals.nonzero_cells),
        "hidden_share_complementary": float(totals.comp_hidden / totals.nonzero_cells),
        "lp_median_width_after_complementary": float(lp.lp_width_median.median()),
        "lp_small_cells_still_narrow": int(lp.lp_within_small_range.sum()),
        "k_sweep": sweep.to_dict("records"), "dp": dp_df.to_dict("records"),
    }
    (REPORTS / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    attrs = {key: {"label": label, "categories": data.categories(people, key)} for key, label in data.ATTRIBUTES.items()}
    WEB_DATA.write_text(json.dumps({"source": metrics["dataset"], "people": metrics["people"], "attributes": attrs,
                                    "tables": web_tables}, separators=(",", ":")), encoding="utf-8")
    findings = {k: metrics[k] for k in ("people", "tables", "k", "suppressed_cells", "recovered_cells",
                                         "recovered_share", "tables_with_recovery", "people_in_recovered_cells",
                                         "complementary_extra_cells", "lp_small_cells_still_narrow")}
    (WEB_DATA.parent / "findings.json").write_text(json.dumps(findings, indent=2), encoding="utf-8")
    write_fixtures(people)
    figures(per_table, sweep, dp_df, people)
    results_md(metrics, per_table)
    return metrics


def write_fixtures(people: pd.DataFrame) -> None:
    """Expected outputs for the dashboard's JavaScript port, checked by `npm test` in web/."""
    cases = []
    for a, b in [("native_country", "race"), ("occupation", "income"), ("education", "race"), ("age_band", "sex")]:
        t, *_ = data.crosstab(people, a, b)
        for k in (5, 11):
            m = suppression.primary(t, k)
            c = suppression.complementary(t, m)
            cases.append({"name": f"{a}|{b}|k={k}", "table": t.tolist(), "k": k,
                          "primary": m.astype(int).tolist(), "complementary": c.astype(int).tolist(),
                          "recovered": attack.propagate(t, m).tolist()})
    FIXTURES.write_text(json.dumps(cases), encoding="utf-8")


def figures(per_table: pd.DataFrame, sweep: pd.DataFrame, dp_df: pd.DataFrame, people: pd.DataFrame) -> None:
    label = lambda r: f"{data.ATTRIBUTES[r.rows]} × {data.ATTRIBUTES[r.cols]}"  # noqa: E731
    top = per_table[per_table.recovered > 0].sort_values("recovered").tail(12)
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    y = np.arange(len(top))
    ax.barh(y, top.suppressed, color=plotstyle.GRID, height=0.62, label="hidden (1–10)")
    ax.barh(y, top.recovered, color=plotstyle.CRITICAL, height=0.62, label="recovered exactly by subtraction")
    ax.set_yticks(y, [label(r) for r in top.itertuples()])
    ax.set_xlabel("Cells")
    ax.set_title("Hidden cells an outsider recovers from the published totals (k = 11)")
    ax.legend(loc="lower right")
    plotstyle.save(fig, FIGURES / "01_recovered_by_table.png")

    fig, ax = plt.subplots(figsize=(6.5, 3.8))
    ax.plot(sweep.k, 100 * sweep.recovered_share, marker="o", color=plotstyle.CRITICAL)
    for r in sweep.itertuples():
        ax.annotate(f"{100 * r.recovered_share:.0f}%", (r.k, 100 * r.recovered_share), xytext=(0, 8),
                    textcoords="offset points", ha="center", fontsize=9)
    ax.set_xticks(sweep.k)
    ax.set_xlabel("Threshold k (cells 1 to k−1 hidden)")
    ax.set_ylabel("Hidden cells recovered (%)")
    ax.set_ylim(0, max(100 * sweep.recovered_share) * 1.3)
    ax.set_title("Raising the threshold does not stop the subtraction attack")
    plotstyle.save(fig, FIGURES / "02_threshold_sweep.png")

    fig, ax1 = plt.subplots(figsize=(7, 3.9))
    ax1.plot(dp_df.epsilon, dp_df.mean_abs_error, marker="o", color=plotstyle.SERIES[0], label="mean absolute error per cell")
    ax1.set_xscale("log")
    ax1.set_xticks(dp_df.epsilon, [f"{e:g}" for e in dp_df.epsilon])
    ax1.set_xlabel("Privacy budget ε (smaller = more private)")
    ax1.set_ylabel("Mean absolute error (people)")
    ax2 = ax1.twinx()
    ax2.plot(dp_df.epsilon, 100 * dp_df.p_attacker_guess_exact, marker="s", color=plotstyle.SERIES[1], label="attacker's best guess correct")
    ax2.set_ylabel("Attacker's best guess correct (%)")
    ax2.spines["right"].set_visible(True)
    ax2.grid(False)
    ax1.set_title("Differential privacy: a few people of error buys real uncertainty")
    lines = ax1.get_lines() + ax2.get_lines()
    ax1.legend(lines, [l.get_label() for l in lines], loc="upper center", fontsize=8)
    plotstyle.save(fig, FIGURES / "03_dp_tradeoff.png")

    t, rlab, clab = data.crosstab(people, "native_country", "race")
    keep = np.argsort(-t.sum(axis=1))[:22]
    t, rlab = t[keep], [rlab[i] for i in keep]
    hidden = suppression.primary(t, K)
    rec = attack.propagate(t, hidden)
    fig, ax = plt.subplots(figsize=(7.6, 7.2))
    shade = np.where(rec >= 0, 2, np.where(hidden, 1, 0))
    cmap = plt.matplotlib.colors.ListedColormap([plotstyle.SURFACE, plotstyle.GRID, "#f4b4ad"])
    ax.imshow(shade, cmap=cmap, aspect="auto", vmin=0, vmax=2)
    for i in range(t.shape[0]):
        for j in range(t.shape[1]):
            text = f"={t[i, j]}" if rec[i, j] >= 0 else ("<11" if hidden[i, j] else f"{t[i, j]:,}")
            ax.text(j, i, text, ha="center", va="center", fontsize=7.5,
                    color=plotstyle.CRITICAL if rec[i, j] >= 0 else plotstyle.INK, weight="bold" if rec[i, j] >= 0 else None)
    ax.set_xticks(range(len(clab)), clab, rotation=20, ha="right")
    ax.set_yticks(range(len(rlab)), rlab)
    ax.grid(False)
    ax.set_title("Country of birth × race: grey = hidden, red = recovered by subtraction")
    plotstyle.save(fig, FIGURES / "04_example_table.png")


def results_md(metrics: dict, per_table: pd.DataFrame) -> None:
    md = lambda f: f.to_markdown(index=False, floatfmt=",.3f")  # noqa: E731
    cols = ["rows", "cols", "suppressed", "recovered", "recovered_share", "comp_hidden", "lp_width_median"]
    lines = ["# Results (auto-generated by scripts/run_audit.py)\n",
             "## Tables with the most recovered cells (k = 11)\n",
             md(per_table.sort_values("recovered", ascending=False)[cols].head(20)),
             f"\n## All metrics\n\n```json\n{json.dumps(metrics, indent=2)}\n```\n"]
    (REPORTS / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
