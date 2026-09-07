"""D7 - Failure 2: a tool-interface failure, in a different layer than
loop control.

Not a loop: the agent behaves perfectly reasonably given what a tool told
it. The tool told it something false. Built as "the working agent, minus
the line-items comparison in check_duplicate's match" - not hypothetical:
CLM-8960's own shipped label in scripts_A.py already names this exact bug
as the reason that case exists: "an agent matching duplicates on member +
hospital + date alone will wrongly escalate this one."

check_duplicate's real, shipped match requires all FOUR facts (member,
hospital, date of service, line items). _BrokenDuplicateMatch below drops
the fourth. CLM-8960 (4 line items, 2026-09-15, Riverside General, member
M-5502) then collides with CLM-8726 in decided_claims - a real, different,
1-line prior claim on the same day, same member, same hospital - and the
weakened tool reports a false MATCH.

Usage: python3 failure2_interface.py
"""

import tools as tools_module
import scripts_A
from agent import ClaimsAgent
from backend import ScriptedBackend
from measure_parallel import MeasuredBackend
from scripts_A import CLAIMS, Call, Final, _render_calls, _render_final

CHEAP_IN, CHEAP_OUT = 0.10, 0.40   # section 7, USD per million tokens


def _cost(input_tokens, output_tokens):
    return input_tokens / 1e6 * CHEAP_IN + output_tokens / 1e6 * CHEAP_OUT


class BrokenDuplicateMatch(tools_module.ClaimsTools):
    """The working agent, minus the line-items comparison. Three facts
    instead of the real four."""

    def check_duplicate(self, member_id, hospital_id, date_of_service, lines):
        for prior in self.decided_claims:
            if (prior["member_id"] == member_id
                    and prior["hospital_id"] == hospital_id
                    and prior["date_of_service"] == date_of_service):
                return (
                    "MATCH: claim {claim_id} was already decided "
                    "({decision}) on {decided_on}. [interface bug: line "
                    "items were never compared.]".format(**prior)
                )
        return "NO MATCH (line items were never compared - broken interface)."


def _script(*turns):
    out = []
    for t in turns:
        out.append(_render_final(t) if isinstance(t, Final)
                  else _render_calls(t))
    return out


def _with_token_estimate(result, backend):
    result.input_tokens_est = round(sum(backend.input_chars_per_turn) / 4)
    result.output_tokens_est = round(sum(backend.output_chars_per_turn) / 4)
    return result


def run_broken():
    """The weakened interface: a confident, wrong escalation."""
    claim = CLAIMS["CLM-8960"]
    broken_tools = BrokenDuplicateMatch(claim)
    script = _script(
        [Call("policy first", "lookup_member_policy", member_id="M-5502")],
        [Call("checking the claims history before pricing four lines",
             "check_duplicate", member_id="M-5502", hospital_id="H-114",
             date_of_service="2026-09-15", lines=claim["lines"])],
        [Call("recording", "issue_decision_letter",
             claim_id="CLM-8960", decision="escalate",
             detail={
                 "trigger": "duplicate_claim",
                 "escalate_to": "human claims assessor",
                 "prior_claim": "CLM-8726",
                 "basis": "check_duplicate returned MATCH for member "
                         "M-5502, hospital H-114, date of service "
                         "2026-09-15.",
             })],
        Final("the claims history shows a match on member, hospital and "
             "date of service; escalating rather than pricing four new "
             "lines against a claim already on file", "escalate", {
                 "trigger": "duplicate_claim",
                 "escalate_to": "human claims assessor",
                 "prior_claim": "CLM-8726",
             }),
    )
    backend = MeasuredBackend(script)
    agent = ClaimsAgent(backend, claim, claim_tools=broken_tools)
    return _with_token_estimate(agent.run(), backend)


def run_fixed():
    """The real, unmodified interface - the shipped D4 trajectory."""
    claim = CLAIMS["CLM-8960"]
    tools_obj = tools_module.ClaimsTools(claim)
    backend = MeasuredBackend(scripts_A.script_for("CLM-8960", parallel=True))
    agent = ClaimsAgent(backend, claim, claim_tools=tools_obj)
    return _with_token_estimate(agent.run(), backend)


def main():
    broken = run_broken()
    fixed = run_fixed()

    print("CLM-8960: a genuine 4-line claim. CLM-8726 (decided_claims) is a "
          "genuine, DIFFERENT, 1-line prior claim - same member, same "
          "hospital, same day, different lines.\n")

    # D4's own answer key for CLM-8960: approve_in_principle, approved_total
    # 1990 (expected_outcomes_A.json) - "Pass" below is graded against this,
    # not against whether the run completed without error.
    broken_pass = broken.decision == "approve_in_principle"
    fixed_pass = fixed.decision == "approve_in_principle" and \
        fixed.detail.get("approved_total") == 1990

    print("--- BEFORE: check_duplicate matches on 3 facts (line items "
          "dropped) ---")
    print("  decision: {}  trigger: {}".format(
        broken.decision, broken.detail.get("trigger")))
    print("  steps: {}  tool_calls: {}  input~{}tok  output~{}tok".format(
        broken.steps, broken.tool_calls, broken.input_tokens_est,
        broken.output_tokens_est))
    print("  pass (vs D4 answer key): {}  guard triggered: none - no "
          "loop-control or gate guard has anything to say about a tool "
          "returning wrong-but-well-formed data".format(broken_pass))
    print("  WRONG: a real, payable claim is escalated on a false "
          "duplicate. The evidence trail (MATCH observation) is real and "
          "the model's reasoning from it is sound - the interface lied.")
    print()

    print("--- AFTER: check_duplicate restored to all 4 facts (shipped, "
          "unmodified) ---")
    print("  decision: {}  approved_total: {}".format(
        fixed.decision, fixed.detail.get("approved_total")))
    print("  steps: {}  tool_calls: {}  input~{}tok  output~{}tok".format(
        fixed.steps, fixed.tool_calls, fixed.input_tokens_est,
        fixed.output_tokens_est))
    print("  pass (vs D4 answer key): {}  guard triggered: none".format(fixed_pass))
    print()

    cost_broken = _cost(broken.input_tokens_est, broken.output_tokens_est)
    cost_fixed = _cost(fixed.input_tokens_est, fixed.output_tokens_est)
    print("The uncomfortable finding: the WRONG run is CHEAPER than the "
          "RIGHT one ({} turns vs {}, {} tool calls vs {}, ${:.6f} vs "
          "${:.6f} cheap-tier) - because escalating early skips pricing "
          "the four lines the correct answer has to price. Turns and cost "
          "alone cannot catch this failure - it PASSES on every "
          "instrumentation signal except the one that checks the actual "
          "outcome; only checking the outcome against the D4 answer key "
          "can.".format(broken.steps, fixed.steps, broken.tool_calls,
                        fixed.tool_calls, cost_broken, cost_fixed))
    print()
    print("Fix layer: the TOOL INTERFACE (check_duplicate's match "
          "criteria), not the prompt and not loop control. A prompt "
          "sentence telling the model to 'also check line items carefully' "
          "would be re-paid every turn of every run forever and could "
          "still be misread; requiring all four facts in the comparison "
          "itself makes the false-positive class of error structurally "
          "impossible.")


if __name__ == "__main__":
    main()
