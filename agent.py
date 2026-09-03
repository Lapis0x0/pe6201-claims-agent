"""The ReAct loop.

One agent, one loop, one model. The loop reasons, acts, observes and repeats
until the model gives a final answer or a guardrail stops it.

The guardrails required by D3a all live here, in code, not in the prompt:

  step cap          MAX_STEPS model turns per run
  budget ceiling    MAX_TOOL_CALLS tool invocations per run
  action dedup      the same tool with the same arguments is refused after
                    MAX_REPEATS attempts
  autonomy gate     the loop will not accept a final answer until the gated
                    action issue_decision_letter has been recorded, and the
                    gate itself lives in tools.check_decision_gate

When a guardrail fires the run does not crash: it escalates to a human claims
assessor with a loop-control trigger, which is the correct behaviour for a
system that cannot finish its own reasoning.
"""

import argparse
import json
import os
from dataclasses import dataclass, field

import config
import tools as tools_module
from backend import LiveBackend, ScriptedBackend


# ---------------------------------------------------------------------------
# parsing
# ---------------------------------------------------------------------------

@dataclass
class ParsedResponse:
    thought: str = ""
    actions: list = field(default_factory=list)   # [(tool_name, args_dict)]
    final_answer: dict = None
    error: str = None


def _extract_json_object(text, start):
    """Read one balanced JSON object from text starting at or after `start`.

    Returns (object, index_after_object), or (None, start) if there is none.
    Brace matching rather than a line-based read, so an Action Input may span
    several lines.
    """
    opening = text.find("{", start)
    if opening == -1:
        return None, start
    depth = 0
    in_string = False
    escaped = False
    for i in range(opening, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[opening:i + 1]), i + 1
                except json.JSONDecodeError:
                    return None, opening + 1
    return None, opening + 1


def parse_react_output(text):
    """Parse one model response into a thought, actions, or a final answer.

    Several Action / Action Input pairs in one response are returned as several
    actions: that is the parallel-call path (D2c). A response carrying both an
    action and a final answer is a parse error, because the two mean different
    things about whether the run is over.
    """
    parsed = ParsedResponse()

    first_thought = text.find("Thought:")
    if first_thought != -1:
        line_end = text.find("\n", first_thought)
        line_end = len(text) if line_end == -1 else line_end
        parsed.thought = text[first_thought + len("Thought:"):line_end].strip()

    final_at = text.find("Final Answer:")
    if final_at != -1:
        obj, _ = _extract_json_object(text, final_at)
        if obj is None:
            parsed.error = (
                "Final Answer must be followed by a single JSON object."
            )
            return parsed
        parsed.final_answer = obj

    cursor = 0
    while True:
        action_at = text.find("Action:", cursor)
        if action_at == -1:
            break
        # "Action Input:" also contains "Action:"; skip that match.
        if text[action_at:action_at + len("Action Input:")] == "Action Input:":
            cursor = action_at + len("Action Input:")
            continue
        line_end = text.find("\n", action_at)
        line_end = len(text) if line_end == -1 else line_end
        name = text[action_at + len("Action:"):line_end].strip()

        input_at = text.find("Action Input:", line_end)
        if input_at == -1:
            parsed.error = (
                "Action {!r} has no Action Input.".format(name)
            )
            return parsed
        args, after = _extract_json_object(text, input_at)
        if args is None:
            parsed.error = (
                "Action Input for {!r} must be a single JSON object.".format(name)
            )
            return parsed
        parsed.actions.append((name, args))
        cursor = after

    if parsed.actions and parsed.final_answer is not None:
        parsed.error = (
            "A response is either actions or a Final Answer, never both."
        )
        parsed.actions = []
        parsed.final_answer = None
    elif not parsed.actions and parsed.final_answer is None:
        parsed.error = (
            "No Action and no Final Answer found."
        )
    return parsed


# ---------------------------------------------------------------------------
# result
# ---------------------------------------------------------------------------

@dataclass
class AgentResult:
    claim_id: str
    decision: str
    detail: dict
    steps: int = 0
    tool_calls: int = 0
    stop_reason: str = "final_answer"
    letter_issued: bool = False
    trace: list = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0

    def summary(self):
        line = "{:<10} {:<22} steps={:<3} tools={:<3} {}".format(
            self.claim_id, self.decision, self.steps, self.tool_calls,
            self.detail.get("trigger", ""),
        )
        return line.rstrip()


# ---------------------------------------------------------------------------
# the agent
# ---------------------------------------------------------------------------

class ClaimsAgent:

    def __init__(self, backend, claim, claim_tools=None,
                 max_steps=config.MAX_STEPS,
                 max_tool_calls=config.MAX_TOOL_CALLS,
                 max_repeats=config.MAX_REPEATS,
                 verbose=False):
        self.backend = backend
        self.claim = claim
        self.tools_obj = claim_tools or tools_module.ClaimsTools(claim)
        self.tools = self.tools_obj.as_dict()
        self.max_steps = max_steps
        self.max_tool_calls = max_tool_calls
        self.max_repeats = max_repeats
        self.verbose = verbose

        self.tool_calls = 0
        self.call_counts = {}
        self.refusals = 0
        self.parse_failures = 0
        self.final_answer_pushbacks = 0

    # -- helpers -----------------------------------------------------------

    def _log(self, text):
        if self.verbose:
            print(text)

    def _call_key(self, name, args):
        return name + " " + json.dumps(args, sort_keys=True, ensure_ascii=False)

    def _dispatch(self, name, args):
        """Run one tool call and return the observation string."""
        if name not in self.tools:
            return (
                "UNKNOWN TOOL {!r}. Available tools: {}.".format(
                    name, ", ".join(self.tools))
            )

        key = self._call_key(name, args)
        self.call_counts[key] = self.call_counts.get(key, 0) + 1
        if self.call_counts[key] > self.max_repeats:
            self.refusals += 1
            return (
                "REFUSED: you have already called {} with these exact "
                "arguments {} times. The records do not change during a run, "
                "so the answer will not change either. Use the observation "
                "you already have.".format(name, self.max_repeats)
            )

        self.tool_calls += 1
        try:
            return str(self.tools[name](**args))
        except NotImplementedError as exc:
            # A tool left as a stub must not take the loop down with it.
            return "TOOL NOT IMPLEMENTED: {} ({}).".format(name, exc)
        except TypeError as exc:
            return (
                "BAD ARGUMENTS for {}: {}. Check the argument names in the "
                "tool list.".format(name, exc)
            )
        except Exception as exc:                      # noqa: BLE001
            return "TOOL ERROR in {}: {}: {}".format(
                name, type(exc).__name__, exc)

    def _escalate(self, trigger, note, steps, messages):
        detail = {"trigger": trigger, "note": note,
                  "escalate_to": "human claims assessor"}
        return AgentResult(
            claim_id=self.claim["claim_id"],
            decision="escalate",
            detail=detail,
            steps=steps,
            tool_calls=self.tool_calls,
            stop_reason=trigger,
            letter_issued=self.tools_obj.letter_issued,
            trace=messages,
            prompt_tokens=getattr(self.backend, "prompt_tokens", 0),
            completion_tokens=getattr(self.backend, "completion_tokens", 0),
        )

    # -- the loop ----------------------------------------------------------

    def run(self):
        messages = [
            {"role": "system", "content": config.build_system_prompt()},
            {"role": "user", "content": config.format_claim_prompt(self.claim)},
        ]

        for step in range(1, self.max_steps + 1):
            response = self.backend.generate(messages)
            messages.append({"role": "assistant", "content": response})
            self._log("\n--- step {} ---\n{}".format(step, response.strip()))

            parsed = parse_react_output(response)

            if parsed.error:
                self.parse_failures += 1
                if self.parse_failures > config.MAX_PARSE_FAILURES:
                    return self._escalate(
                        "unparseable_model_output",
                        "the model produced {} responses in a row that did not "
                        "follow the output format".format(self.parse_failures),
                        step, messages)
                messages.append({
                    "role": "user",
                    "content": (
                        "Format error: {} Reply with either Thought/Action/"
                        "Action Input, or Thought/Final Answer.".format(
                            parsed.error)
                    ),
                })
                continue
            self.parse_failures = 0

            if parsed.final_answer is not None:
                result = self._finalise(parsed.final_answer, step, messages)
                if result is not None:
                    return result
                continue

            # budget ceiling, checked before spending it
            if self.tool_calls + len(parsed.actions) > self.max_tool_calls:
                return self._escalate(
                    "budget_cap_exceeded",
                    "the run reached its ceiling of {} tool calls before "
                    "reaching a decision".format(self.max_tool_calls),
                    step, messages)

            observations = []
            for name, args in parsed.actions:
                observation = self._dispatch(name, args)
                self._log("Observation ({}): {}".format(name, observation))
                observations.append(
                    "Observation [{}]: {}".format(name, observation))

            if self.refusals > self.max_repeats:
                return self._escalate(
                    "repeated_action",
                    "the run kept re-issuing tool calls it had already made",
                    step, messages)

            messages.append({"role": "user", "content": "\n".join(observations)})

        return self._escalate(
            "step_cap_exceeded",
            "the run reached its cap of {} steps without a "
            "decision".format(self.max_steps),
            self.max_steps, messages)

    def _finalise(self, final_answer, step, messages):
        """Accept the final answer, or push back once and return None."""
        decision = final_answer.get("decision")
        detail = final_answer.get("detail") or {}

        if decision not in config.DECISIONS:
            self.final_answer_pushbacks += 1
            if self.final_answer_pushbacks > config.MAX_PARSE_FAILURES:
                return self._escalate(
                    "unparseable_model_output",
                    "the final answer never named one of the three allowed "
                    "decisions",
                    step, messages)
            messages.append({"role": "user", "content": (
                "Your Final Answer must name one of: {}. Try "
                "again.".format(", ".join(config.DECISIONS))
            )})
            return None

        # Autonomy gate: the record is the decision. No record, no decision.
        if not self.tools_obj.letter_issued:
            self.final_answer_pushbacks += 1
            if self.final_answer_pushbacks > config.MAX_PARSE_FAILURES:
                return self._escalate(
                    "gate_not_satisfied",
                    "the run gave a final answer without recording a decision "
                    "letter, and did not correct it when told",
                    step, messages)
            messages.append({"role": "user", "content": (
                "You have not issued the decision letter. Call "
                "issue_decision_letter with this decision first, then give "
                "your Final Answer."
            )})
            return None

        return AgentResult(
            claim_id=self.claim["claim_id"],
            decision=decision,
            detail=detail,
            steps=step,
            tool_calls=self.tool_calls,
            stop_reason="final_answer",
            letter_issued=True,
            trace=messages,
            prompt_tokens=getattr(self.backend, "prompt_tokens", 0),
            completion_tokens=getattr(self.backend, "completion_tokens", 0),
        )


# ---------------------------------------------------------------------------
# single-claim CLI, for looking at one run in detail
# ---------------------------------------------------------------------------

def load_claim(claim_id):
    for claim in tools_module.load_table("claims"):
        if claim["claim_id"] == claim_id:
            return claim
    raise SystemExit("no claim {} in data_A/claims.json".format(claim_id))


def main():
    parser = argparse.ArgumentParser(description="Run the agent on one claim.")
    parser.add_argument("claim_id")
    parser.add_argument("--live", action="store_true",
                        help="use a real model instead of the scripted backend")
    parser.add_argument("--model", default=config.DEFAULT_MODEL)
    parser.add_argument("--api-key", default=os.environ.get("OPENROUTER_API_KEY"))
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    claim = load_claim(args.claim_id)
    if args.live:
        backend = LiveBackend(model=args.model, api_key=args.api_key)
    else:
        import scripts_A
        backend = ScriptedBackend(scripts_A.script_for(args.claim_id))

    result = ClaimsAgent(backend, claim, verbose=not args.quiet).run()
    print("\n=== result ===")
    print(result.summary())
    print(json.dumps(result.detail, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
