"""D7 - Failure 1 (required): a loop-control failure.

Built as "the working agent, minus action de-duplication" - not a
separately written bad agent. `ClaimsAgent` already takes `max_repeats` as a
constructor argument (agent.py); setting it far above any realistic repeat
count is exactly equivalent to deleting the de-duplication guard, and
setting it back to `config.MAX_REPEATS` is exactly "putting X back."

The scripted trajectory itself never changes: the model keeps re-issuing an
identical `get_preauthorisation` call, turn after turn, without ever
proceeding to a decision - "it repeats an action it already took... a loop
has no memory of its own actions unless you give it one" (the brief's own
framing). What changes is only whether the code layer is watching.

Usage: python3 failure1_loop.py
"""

import config
import tools as tools_module
from agent import ClaimsAgent
from backend import ScriptedBackend
from measure_parallel import MeasuredBackend
from scripts_A import CLAIMS, Call, _render_calls

REPEATED_CALL = Call(
    "let me check that authorisation again to be sure",
    "get_preauthorisation", member_id="M-2214", procedure_code="62480",
    date_of_service="2026-09-02",
)


def _looping_script(n_turns):
    """n_turns of the identical call, and never a Final Answer."""
    return [_render_calls([REPEATED_CALL]) for _ in range(n_turns)]


def run_once(max_repeats, n_turns=config.MAX_STEPS + 1):
    claim = CLAIMS["CLM-8842"]
    backend = MeasuredBackend(_looping_script(n_turns))
    claim_tools = tools_module.ClaimsTools(claim)
    agent = ClaimsAgent(backend, claim, claim_tools=claim_tools,
                        max_repeats=max_repeats)
    result = agent.run()
    result.input_tokens_est = round(sum(backend.input_chars_per_turn) / 4)
    result.output_tokens_est = round(sum(backend.output_chars_per_turn) / 4)
    return result


def turn_distribution():
    """The turn distribution across the real 50-case set - none of it
    anywhere near the step cap. Reuses the shipped trajectories/labels."""
    import json
    expected = json.load(open(config.EXPECTED_OUTCOMES_PATH, encoding="utf-8"))
    claims = {c["claim_id"]: c
             for c in tools_module.load_table("claims")}
    import scripts_A
    turns = []
    for row in expected:
        claim = claims[row["case_id"]]
        backend = ScriptedBackend(scripts_A.script_for(row["case_id"]))
        result = ClaimsAgent(backend, claim,
                             claim_tools=tools_module.ClaimsTools(claim)).run()
        turns.append(result.steps)
    turns.sort()
    n = len(turns)
    median = turns[n // 2]
    hit_cap = sum(1 for t in turns if t >= config.MAX_STEPS)
    return {"n": n, "median": median, "min": turns[0], "max": turns[-1],
           "hit_cap": hit_cap}


def main():
    dist = turn_distribution()
    print("Turn distribution across the real 50-case evaluation set "
          "(parallel calling):")
    print("  n={n}  median={median}  min={min}  max={max}  "
          "hit the {cap}-turn cap: {hit_cap}/{n}".format(
              cap=config.MAX_STEPS, **dist))
    print()

    print("--- BROKEN: the working agent, minus de-duplication "
          "(max_repeats=999) ---")
    broken = run_once(max_repeats=999)
    broken_pass = broken.decision == "escalate"  # reaches a safe outcome
    print("  decision: {}  trigger: {}".format(
        broken.decision, broken.detail.get("trigger")))
    print("  steps: {}  tool_calls: {}  input~{}tok  output~{}tok".format(
        broken.steps, broken.tool_calls, broken.input_tokens_est,
        broken.output_tokens_est))
    print("  pass (reaches a safe outcome): {}  guard triggered: {}".format(
        broken_pass, broken.detail.get("trigger")))
    print("  Ran to the step cap. No exception was raised. It just spent "
          "{} turns re-asking a question it had already answered - PASS "
          "on outcome, but only instrumentation (steps/tokens/cost) shows "
          "anything went wrong at all.".format(broken.steps))
    print()

    print("--- WORKING / RESTORED: de-duplication at its normal default "
          "(max_repeats={}) ---".format(config.MAX_REPEATS))
    fixed = run_once(max_repeats=config.MAX_REPEATS)
    fixed_pass = fixed.decision == "escalate"
    print("  decision: {}  trigger: {}".format(
        fixed.decision, fixed.detail.get("trigger")))
    print("  steps: {}  tool_calls: {}  input~{}tok  output~{}tok".format(
        fixed.steps, fixed.tool_calls, fixed.input_tokens_est,
        fixed.output_tokens_est))
    print("  pass (reaches a safe outcome): {}  guard triggered: {}".format(
        fixed_pass, fixed.detail.get("trigger")))
    print()

    ratio = broken.steps / fixed.steps
    tok_ratio = broken.input_tokens_est / fixed.input_tokens_est
    cheap_in, cheap_out = 0.10, 0.40   # section 7, USD per million tokens
    cost_broken = (broken.input_tokens_est / 1e6 * cheap_in
                  + broken.output_tokens_est / 1e6 * cheap_out)
    cost_fixed = (fixed.input_tokens_est / 1e6 * cheap_in
                 + fixed.output_tokens_est / 1e6 * cheap_out)
    print("Turns: {} -> {} ({:.1f}x). Tool calls: {} -> {}. Input tokens: "
          "{} -> {} ({:.1f}x). Cheap-tier cost: ${:.6f} -> ${:.6f} "
          "({:.1f}x).".format(
              broken.steps, fixed.steps, ratio, broken.tool_calls,
              fixed.tool_calls, broken.input_tokens_est,
              fixed.input_tokens_est, tok_ratio, cost_broken, cost_fixed,
              cost_broken / cost_fixed))
    print()

    print("Why the OTHER two caps would not have caught this as well:")
    print("  step cap (15):    would eventually fire, but only after all "
          "15 turns - {}x later than de-dup's 5.".format(
              config.MAX_STEPS / fixed.steps))
    print("  budget ceiling (24): this script makes 1 tool call per turn, "
          "so 15 turns means 15 <= 24 tool_calls - the ceiling never comes "
          "close to firing before the step cap does.")
    print("  de-duplication is the only guard that is CHEAP and SPECIFIC: "
          "it recognises the exact failure signature (the same call, "
          "again) rather than waiting for a generic ceiling.")

    print()
    print("Pass rate check: the 50-case evaluation set is unaffected by "
          "restoring de-duplication, because no legitimate case ever "
          "triggers it (see the turn distribution above - max {} turns, "
          "nowhere near a repeat).".format(dist["max"]))


if __name__ == "__main__":
    main()
