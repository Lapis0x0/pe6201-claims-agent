"""D6 - the cost-to-serve model, Class 5's three layers.

Layer 1 (variable) and the success rate `p` behind Layer 2 are computed
directly from this repository's real result files - the five D5(b) live
batteries (results/d5b_live_*.json) plus the D2(b) v1/v2 pair
(results/d2b_live_*.json) and the scripted D2(c) parallel/sequential
measurement (measure_parallel.py). Nothing here is hand-typed where a real
number is obtainable from a committed results file.

Run: python3 d6_cost_model.py
"""

import json
import os

import config
from harness import PRICE_PER_MILLION
from measure_parallel import measure_all

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")

# ---------------------------------------------------------------------------
# Problem A's given inputs (Appendix A)
# ---------------------------------------------------------------------------

VOLUME_PER_MONTH = 8000
FAILURE_COST = 38.0 * 12 / 60           # claims assessor, $38/h, 12 min = $7.60

# Layer 3: no server (fixture files + a scripted harness cost nothing to
# run). The only recurring cost is a periodic live re-run of the evaluation
# battery for regression monitoring - assume monthly, on the cheapest
# measured model, 40 cases x 1 trial. STATED ASSUMPTION, not a measurement;
# the brief does not fix a figure for this layer.
LAYER_3_MONTHLY = 5.00

# Operational cap per policy member, stated as required by D6.  At the
# selected model's measured expected cost ($0.2909/claim), US$1 funds three
# average claims in a calendar month.  A fourth claim is routed to the normal
# human process before further AI spend.  This is a cost-model/governance
# assumption, not a database feature (persistent user accounts are out of
# scope for A2).
MONTHLY_PER_USER_SPEND_CAP = 1.00

# The five D5(b) models plus the two D2(b) prompt-version runs, each
# resolved straight from its committed --json evidence file.
RUNS = {
    "gemini-2.5-flash":      ("google/gemini-2.5-flash", "d5b_live_gemini_2.5_flash.json"),
    "deepseek-v4-flash":     ("deepseek/deepseek-v4-flash", "d5b_live_deepseek_v4_flash.json"),
    "gpt-4o-mini":           ("openai/gpt-4o-mini", "d2b_live_v2_gpt4o_mini.json"),
    "gpt-4o-mini (v1 prompt)": ("openai/gpt-4o-mini", "d2b_live_v1_gpt4o_mini.json"),
    "qwen-2.5-7b-instruct":  ("qwen/qwen-2.5-7b-instruct", "d5b_live_qwen_2.5_7b_instruct.json"),
    "llama-3.1-8b-instruct": ("meta-llama/llama-3.1-8b-instruct", "d5b_live_llama_3.1_8b_instruct.json"),
}


def _trial_level_pass_rate(rows):
    """FAQ-defined pass rate: passing trials divided by total trials."""
    return sum(bool(r["passed"]) for r in rows) / len(rows)


def measure_run(model, filename):
    """(p, input_tokens_per_run, output_tokens_per_run, l1_per_run,
    latency_per_run) for one committed live-battery result file, all
    computed from the file itself - not estimated, not hand-copied."""
    path = os.path.join(RESULTS_DIR, filename)
    rows = json.load(open(path, encoding="utf-8"))
    n = len(rows)
    p = _trial_level_pass_rate(rows)
    tin = sum(r.get("prompt_tokens") or 0 for r in rows) / n
    tout = sum(r.get("completion_tokens") or 0 for r in rows) / n
    latency = sum(r.get("runtime_seconds") or 0 for r in rows) / n
    price_in, price_out = PRICE_PER_MILLION[model]
    l1 = tin / 1e6 * price_in + tout / 1e6 * price_out
    return {"p": p, "input_tokens": tin, "output_tokens": tout, "l1": l1,
            "latency": latency}


def layer1_variable(input_tokens, output_tokens, model):
    price_in, price_out = PRICE_PER_MILLION[model]
    return input_tokens / 1e6 * price_in + output_tokens / 1e6 * price_out


def layer2_fallback(success_rate):
    return (1 - success_rate) * FAILURE_COST


def cost_per_successful_task(l1_per_run, success_rate):
    return l1_per_run + layer2_fallback(success_rate)


def monthly_cost(l1_per_run, success_rate, volume=VOLUME_PER_MONTH):
    return cost_per_successful_task(l1_per_run, success_rate) * volume + LAYER_3_MONTHLY


def break_even_success_rate(cheap_l1_per_run, expensive_success_rate, expensive_l1_per_run):
    """The success rate the cheap model needs to match the expensive one's
    TOTAL (Layer 1 + Layer 2) cost per run."""
    e = expensive_l1_per_run + (1 - expensive_success_rate) * FAILURE_COST
    affordable_failures = (e - cheap_l1_per_run) / FAILURE_COST
    return 1 - affordable_failures


def main():
    measured = {name: measure_run(model, fname) for name, (model, fname) in RUNS.items()}

    print("Shipping caps: {} model turns/run; {} tool calls/run; "
          "${:.2f}/policy member/month".format(
              config.MAX_STEPS,
              config.MAX_TOOL_CALLS,
              MONTHLY_PER_USER_SPEND_CAP))
    print()

    print("Per-model measured numbers (real, from results/*.json):")
    print("{:<26}{:>8}{:>12}{:>12}{:>10}".format(
        "model", "p", "in tok/run", "out tok/run", "L1/run"))
    for name, d in measured.items():
        print("{:<26}{:>8.1%}{:>12.0f}{:>12.0f}{:>10.5f}".format(
            name, d["p"], d["input_tokens"], d["output_tokens"], d["l1"]))
    print()

    print("D6 outputs - cost/task, fallback cost/task, total expected "
          "cost/task, monthly cost @ {}/mo:".format(VOLUME_PER_MONTH))
    print("{:<26}{:>10}{:>10}{:>12}{:>16}".format(
        "model", "L1/task", "L2/task", "total/task", "monthly"))
    ranked = sorted(
        ((name, d) for name, d in measured.items() if "v1 prompt" not in name),
        key=lambda kv: kv[1]["l1"] + layer2_fallback(kv[1]["p"]))
    for name, d in ranked:
        l2 = layer2_fallback(d["p"])
        total = d["l1"] + l2
        m = monthly_cost(d["l1"], d["p"])
        print("{:<26}{:>10.5f}{:>10.4f}{:>12.4f}{:>16.2f}".format(
            name, d["l1"], l2, total, m))
    print()

    # -- Sensitivity: +-10pp around the baseline model (gpt-4o-mini) -------
    base = measured["gpt-4o-mini"]
    p0 = base["p"]
    print("Sensitivity: gpt-4o-mini's measured p={:.1%}, +-10pp:".format(p0))
    print("{:<12}{:>8}{:>14}{:>18}{:>16}".format(
        "", "p", "layer2", "cost/success", "monthly"))
    for label, p in (("downside", max(0.0, p0 - 0.10)),
                      ("measured", p0),
                      ("upside", min(1.0, p0 + 0.10))):
        l2 = layer2_fallback(p)
        cps = cost_per_successful_task(base["l1"], p)
        m = monthly_cost(base["l1"], p)
        print("{:<12}{:>8.1%}{:>14.4f}{:>18.4f}{:>16.2f}".format(label, p, l2, cps, m))
    print()

    # -- Break-even: every other model vs the strongest (gemini) -----------
    exp_name = "gemini-2.5-flash"
    exp = measured[exp_name]
    print("Break-even success rate: what would each OTHER model need to "
          "reach to match {}'s total cost/task (p={:.1%}, L1=${:.5f}/run)?".format(
              exp_name, exp["p"], exp["l1"]))
    for name, d in measured.items():
        if name == exp_name or "v1 prompt" in name:
            continue
        be = break_even_success_rate(d["l1"], exp["p"], exp["l1"])
        gap = be - d["p"]
        print("  {:<24} needs p={:.1%} (currently {:.1%}, gap {:+.1%})".format(
            name, be, d["p"], gap))


if __name__ == "__main__":
    main()
