"""D2(c) — measure parallel vs. sequential tool-calling, exactly.

The brief's input ~= B*T + D*T(T-1)/2 assumes a uniform per-turn addition D.
We don't have to assume it: the scripted backend produces real text for
every turn, so this script replays every case both ways and sums the actual
length of the message list sent to the backend at every turn - the exact
quantity the formula approximates. No live call, no estimate.

Usage: python3 measure_parallel.py [--json out.json]
"""

import argparse
import json

import config
import scripts_A
import tools as tools_module
from agent import ClaimsAgent
from backend import ScriptedBackend


class MeasuredBackend(ScriptedBackend):
    """ScriptedBackend that also logs the input sent, and output returned,
    at every turn."""

    def __init__(self, script):
        super().__init__(script)
        self.input_chars_per_turn = []
        self.output_chars_per_turn = []

    def generate(self, messages):
        self.input_chars_per_turn.append(
            sum(len(m["content"]) for m in messages))
        response = super().generate(messages)
        self.output_chars_per_turn.append(len(response))
        return response


def run_one(claim_id, claim, parallel):
    script = scripts_A.script_for(claim_id, parallel=parallel)
    backend = MeasuredBackend(script)
    claim_tools = tools_module.ClaimsTools(claim)
    agent = ClaimsAgent(backend, claim, claim_tools=claim_tools)
    result = agent.run()
    total_input_chars = sum(backend.input_chars_per_turn)
    total_output_chars = sum(backend.output_chars_per_turn)
    return {
        "turns": result.steps,
        "tool_calls": result.tool_calls,
        "input_chars": total_input_chars,
        "input_tokens_est": round(total_input_chars / 4),
        "output_chars": total_output_chars,
        "output_tokens_est": round(total_output_chars / 4),
    }


def measure_all():
    """Run every case both ways; return (rows, totals). Importable by D6."""
    expected_by_id = json.load(open(config.EXPECTED_OUTCOMES_PATH,
                                    encoding="utf-8"))
    case_ids = [row["case_id"] for row in expected_by_id]
    claims = {c["claim_id"]: c
             for c in tools_module.load_table("claims")}

    rows = []
    for case_id in case_ids:
        claim = claims[case_id]
        par = run_one(case_id, claim, parallel=True)
        seq = run_one(case_id, claim, parallel=False)
        rows.append({"case_id": case_id, "parallel": par, "sequential": seq})

    totals = {
        mode: {
            "input_tokens": sum(r[mode]["input_tokens_est"] for r in rows),
            "output_tokens": sum(r[mode]["output_tokens_est"] for r in rows),
            "turns": sum(r[mode]["turns"] for r in rows),
        }
        for mode in ("parallel", "sequential")
    }
    return rows, totals


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", default=None)
    args = parser.parse_args()

    rows, totals = measure_all()

    b_chars = len(config.build_system_prompt())
    print("system prompt B: {} chars (~{} tokens)\n".format(
        b_chars, round(b_chars / 4)))

    print("{:<10} {:>8} {:>8} {:>10} {:>10} {:>8} {:>8} {:>10} {:>10}".format(
        "case", "T_par", "T_seq", "tok_par", "tok_seq", "calls_p", "calls_s",
        "saved_tok", "saved_%"))
    print("-" * 100)
    tot_par = tot_seq = 0
    for row in rows:
        p, s = row["parallel"], row["sequential"]
        saved = s["input_tokens_est"] - p["input_tokens_est"]
        pct = saved / s["input_tokens_est"] * 100 if s["input_tokens_est"] else 0
        tot_par += p["input_tokens_est"]
        tot_seq += s["input_tokens_est"]
        print("{:<10} {:>8} {:>8} {:>10} {:>10} {:>8} {:>8} {:>10} {:>9.1f}%".format(
            row["case_id"], p["turns"], s["turns"],
            p["input_tokens_est"], s["input_tokens_est"],
            p["tool_calls"], s["tool_calls"], saved, pct))

    print("-" * 100)
    saved_total = tot_seq - tot_par
    print("TOTAL input across {} cases: parallel {} tokens, sequential {} "
          "tokens, saved {} tokens ({:.1f}%)".format(
              len(rows), tot_par, tot_seq, saved_total,
              saved_total / tot_seq * 100 if tot_seq else 0))
    print("TOTAL output across {} cases: parallel {} tokens, sequential {} "
          "tokens".format(len(rows), totals["parallel"]["output_tokens"],
                          totals["sequential"]["output_tokens"]))

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(rows, fh, indent=2)
        print("\nper-case rows written to {}".format(args.json))


if __name__ == "__main__":
    main()
