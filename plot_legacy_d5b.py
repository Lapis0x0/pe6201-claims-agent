"""Regenerate the two historical D5(b) before/after figures."""

import json
import os
from collections import Counter
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/pe6201-matplotlib")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
FIGS = ROOT / "figs"
BLUE = "#78A6C8"
CORAL = "#E07A5F"
GREY = "#8B9098"


def strict_case_rate(rows):
    by_case = {}
    for row in rows:
        by_case.setdefault(row["case_id"], []).append(row)
    return 100 * sum(all(r["passed"] for r in case) for case in by_case.values()) / len(by_case)


def main():
    before = json.loads((RESULTS / "d5b_live_gpt4o_mini_full_battery.json").read_text())
    after = json.loads((RESULTS / "d5b_live_validation_after_prompt_fix.json").read_text())
    before_rate, after_rate = strict_case_rate(before), strict_case_rate(after)
    before_turns = sorted(r["steps"] for r in before)[len(before) // 2]
    after_turns = sorted(r["steps"] for r in after)[len(after) // 2]

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    axes[0].bar(["before fix", "after fix"], [before_rate, after_rate], color=[CORAL, BLUE])
    axes[0].set_ylim(0, 100)
    axes[0].set_ylabel("strict case-consistency rate (%)")
    axes[0].set_title("D5(b) - GPT-4o-mini outcome consistency")
    for i, value in enumerate((before_rate, after_rate)):
        axes[0].text(i, value + 1, f"{value:.0f}%", ha="center")

    axes[1].bar(["before fix", "after fix"], [before_turns, after_turns], color=[CORAL, BLUE])
    axes[1].axhline(5, linestyle="--", color=GREY, label="scripted assumption (5)")
    axes[1].set_ylabel("median turns")
    axes[1].set_title("D5(b) - median turns vs. scripted assumption")
    axes[1].legend()
    for i, value in enumerate((before_turns, after_turns)):
        axes[1].text(i, value + 0.1, str(value), ha="center")
    fig.tight_layout()
    fig.savefig(FIGS / "fig_d5b_before_after.png", dpi=180)
    plt.close(fig)

    failures = [r for r in after if not r["passed"]]
    reasons = Counter(r.get("stop_reason") or "unknown" for r in failures)
    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    labels, values = list(reasons), list(reasons.values())
    ax.bar(labels, values, color=CORAL)
    ax.set_ylabel("failing trials")
    ax.set_title("D5(b) - why the remaining failures happen")
    ax.tick_params(axis="x", rotation=18)
    for i, value in enumerate(values):
        ax.text(i, value + 0.15, str(value), ha="center")
    fig.tight_layout()
    fig.savefig(FIGS / "fig_d5b_failure_reasons.png", dpi=180)
    plt.close(fig)
    print("regenerated fig_d5b_before_after.png and fig_d5b_failure_reasons.png")


if __name__ == "__main__":
    main()
