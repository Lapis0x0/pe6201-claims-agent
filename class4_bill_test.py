"""Completed-task cost test: token cost per useful output.

This is the retry-until-success diagnostic C_run / p. It is deliberately
separate from D6's Class 5 escalation model C_run + (1-p)*failure_cost.
All values come from the canonical D5 live result files and price table.
"""

import json
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/pe6201-matplotlib")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from d6_cost_model import RUNS, measure_run

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "figs" / "fig_d0_class4_bill_test.png"


def measurements():
    rows = []
    for label, (model, filename) in RUNS.items():
        if "v1 prompt" in label:
            continue
        measured = measure_run(model, filename)
        result_rows = json.loads((ROOT / "results" / filename).read_text())
        negative_rows = [
            row for row in result_rows
            if row["expected"] != "approve_in_principle"
        ]
        run_cost = measured["l1"]
        # The required denominator is the negative-case
        # success rate, not the happy-path rate.
        p = sum(bool(row["passed"]) for row in negative_rows) / len(negative_rows)
        rows.append({
            "model": label,
            "trials": len(negative_rows),
            "pass_rate": p,
            "run_cost": run_cost,
            "cost_per_completed": run_cost / p,
        })
    return rows


def make_plot(rows):
    labels = [r["model"].replace("-instruct", "") for r in rows]
    run_costs = [r["run_cost"] for r in rows]
    completed_costs = [r["cost_per_completed"] for r in rows]
    x = range(len(rows))

    fig, ax = plt.subplots(figsize=(10.5, 5.8))
    width = 0.36
    ax.bar([i - width / 2 for i in x], run_costs, width,
           label="Measured token cost / run", color="#78A6C8")
    ax.bar([i + width / 2 for i in x], completed_costs, width,
           label="Cost / completed output (C / p)", color="#E07A5F")
    ax.set_xticks(list(x), labels, rotation=18, ha="right")
    ax.set_ylabel("US dollars")
    ax.set_title("Completed-task cost: failed runs raise the cost of useful output")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=False)
    for i, row in enumerate(rows):
        ax.text(i + width / 2, row["cost_per_completed"] + 0.00008,
                "${:.4f}\n(p={:.1%})".format(
                    row["cost_per_completed"], row["pass_rate"]),
                ha="center", va="bottom", fontsize=8)
    ax.text(0.01, -0.31,
            "C/p assumes failed runs are retried. D6 instead prices escalation "
            "as C + (1-p) x $7.60; the two answer different questions.",
            transform=ax.transAxes, fontsize=9, color="#444444")
    fig.tight_layout()
    fig.savefig(OUTPUT, dpi=180, bbox_inches="tight")


def main():
    rows = measurements()
    print("Completed-task cost test: C_run / p")
    print("{:<26}{:>10}{:>12}{:>16}".format(
            "model", "p (negative)", "C/run", "C/completed"))
    for row in rows:
        print("{:<26}{:>10.2%}{:>12.5f}{:>16.5f}".format(
            row["model"], row["pass_rate"], row["run_cost"],
            row["cost_per_completed"]))
    make_plot(rows)
    print("\nplot written to", OUTPUT)


if __name__ == "__main__":
    main()
