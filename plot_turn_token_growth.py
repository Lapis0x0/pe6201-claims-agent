"""Plot predicted input-token growth as agent turns increase."""

import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/pe6201-matplotlib")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "figs" / "fig_d0_turn_token_growth.png"
B = 2165  # measured system-prompt prefix, tokens
D = 176   # median inferred growth/turn, current parallel trajectories


def predicted_input(turns):
    """Exact finite-sum form corresponding to B*T + D*T^2/2."""
    return B * turns + D * turns * (turns - 1) / 2


def main():
    turns = list(range(1, 17))
    prefix = [B * t for t in turns]
    history = [D * t * (t - 1) / 2 for t in turns]
    totals = [predicted_input(t) for t in turns]

    fig, ax = plt.subplots(figsize=(10.5, 5.8))
    ax.stackplot(turns, prefix, history,
                 labels=["Repeated base prompt: B x T",
                         "Accumulated history: D x T(T-1) / 2"],
                 colors=["#78A6C8", "#E07A5F"], alpha=0.9)
    ax.plot(turns, totals, color="#273043", linewidth=2.2,
            marker="o", markersize=3, label="Total predicted input")
    for t in (4, 8, 16):
        total = predicted_input(t)
        ax.annotate(f"{t} turns\n{total:,.0f} tokens", (t, total),
                    xytext=((-28 if t == 16 else 0), 10),
                    textcoords="offset points",
                    ha="center", fontsize=9, fontweight="bold")
    ratio = predicted_input(16) / predicted_input(8)
    ax.text(0.02, 0.94, f"8 -> 16 turns: {ratio:.1f}x input tokens",
            transform=ax.transAxes, fontsize=11, fontweight="bold",
            bbox={"boxstyle": "round,pad=0.35", "facecolor": "white",
                  "edgecolor": "#777777", "alpha": 0.9})
    ax.set_title("Input-token growth as agent turns increase")
    ax.set_xlabel("Agent turns (T)")
    ax.set_ylabel("Predicted input tokens across one run")
    ax.set_xticks(turns)
    ax.set_ylim(0, max(totals) * 1.08)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=False, loc="upper left", bbox_to_anchor=(0, 0.84))
    ax.text(0.01, -0.20,
            "Formula: B x T + D x T(T-1)/2. Measured B = 2,165; "
            "representative D = 176 tokens/turn (median, parallel trajectories).",
            transform=ax.transAxes, fontsize=9, color="#444444")
    fig.tight_layout()
    OUTPUT.parent.mkdir(exist_ok=True)
    fig.savefig(OUTPUT, dpi=180, bbox_inches="tight")
    print(f"B={B}, D={D}; T=8: {predicted_input(8):,.0f}; "
          f"T=16: {predicted_input(16):,.0f}; ratio={ratio:.2f}x")
    print("plot written to", OUTPUT)


if __name__ == "__main__":
    main()
