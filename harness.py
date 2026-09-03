"""The evaluation harness.

Runs the agent over the evaluation set and scores it against the answer key.

Two kinds of check, as the brief requires:

  code check       decision, and for escalations the trigger, are compared to
                   expected_outcomes_A.json by this script. No model, no human.
                   Both fields come from fixed vocabularies, which is what
                   makes them code-checkable.

  judgement check  the answer key's `must_record` items are prose about what
                   the decision record has to say. They are printed next to
                   the run's own record for a human or a second model to
                   judge, and are deliberately NOT scored here. Whether
                   "PA-5640 found, its validity ended 2026-05-31" is present in
                   a written justification is not a string comparison.

Every reported pass rate carries its trial count.

    python3 harness.py                      scripted backend, all cases, 1 trial
    python3 harness.py --sequential         same trajectories, one action per turn
    python3 harness.py --trials 3           three trials per case
    python3 harness.py --case CLM-8894      one case, with the full trace
    python3 harness.py --live --model M     a real model through OpenRouter
"""

import argparse
import json
import os
import sys
from collections import Counter

import config
import scripts_A
import tools as tools_module
from agent import ClaimsAgent
from backend import LiveBackend, ScriptedBackend


def load_expected(path=config.EXPECTED_OUTCOMES_PATH):
    with open(path, encoding="utf-8") as fh:
        return {row["case_id"]: row for row in json.load(fh)}


def check(result, expected):
    """The code check. Returns (passed, reason)."""
    if result.decision != expected["expected_decision"]:
        return False, "expected {}, got {}".format(
            expected["expected_decision"], result.decision)
    wanted_trigger = expected.get("trigger")
    if wanted_trigger:
        got = result.detail.get("trigger")
        if got != wanted_trigger:
            return False, "expected trigger {}, got {}".format(
                wanted_trigger, got)
    return True, ""


def run_evaluation(backend_factory, cases, expected_by_id, trials=1,
                   verbose=False):
    """Run every case `trials` times and score each run against the key."""
    rows = []
    for claim in cases:
        case_id = claim["claim_id"]
        expected = expected_by_id[case_id]
        for trial in range(1, trials + 1):
            claim_tools = tools_module.ClaimsTools(claim)
            agent = ClaimsAgent(backend_factory(claim), claim,
                                claim_tools=claim_tools, verbose=verbose)
            result = agent.run()
            passed, reason = check(result, expected)
            rows.append({
                "case_id": case_id,
                "trial": trial,
                "family": expected.get("family", ""),
                "expected": expected["expected_decision"],
                "expected_trigger": expected.get("trigger"),
                "actual": result.decision,
                "actual_trigger": result.detail.get("trigger"),
                "passed": passed,
                "reason": reason,
                "steps": result.steps,
                "tool_calls": result.tool_calls,
                "stop_reason": result.stop_reason,
                "letter_issued": result.letter_issued,
                "must_record": expected.get("must_record", []),
                "detail": result.detail,
                "prompt_tokens": result.prompt_tokens,
                "completion_tokens": result.completion_tokens,
            })
    return rows


def report(rows, label, trials):
    print()
    print("case       trial  expected              actual                "
          "steps tools  result")
    print("-" * 92)
    for row in rows:
        print("{case_id:<10} {trial:<6} {expected:<21} {actual:<21} "
              "{steps:<5} {tools:<6} {mark}{note}".format(
                  case_id=row["case_id"], trial=row["trial"],
                  expected=row["expected"], actual=row["actual"],
                  steps=row["steps"], tools=row["tool_calls"],
                  mark="PASS" if row["passed"] else "FAIL",
                  note="" if row["passed"] else "  (" + row["reason"] + ")"))

    passed = sum(r["passed"] for r in rows)
    total = len(rows)
    print("-" * 92)
    print("backend: {}".format(label))
    print("pass rate: {:.1%}  ({}/{} runs; {} cases x {} "
          "trial{})".format(passed / total if total else 0.0, passed, total,
                            total // trials if trials else 0, trials,
                            "" if trials == 1 else "s"))

    steps = [r["steps"] for r in rows]
    if steps:
        median = sorted(steps)[len(steps) // 2]
        print("turns: median {}, min {}, max {}".format(
            median, min(steps), max(steps)))
    stops = Counter(r["stop_reason"] for r in rows if not r["passed"])
    if stops:
        print("failure stop reasons: {}".format(dict(stops)))

    failures = [r for r in rows if not r["passed"]]
    if failures:
        print("\nfailures:")
        for row in failures:
            print("  {} trial {}: {}".format(
                row["case_id"], row["trial"], row["reason"]))
    return passed, total


def print_judgement_sheet(rows):
    """Print each run's record beside the key's must_record items.

    This is the input to the judgement check; nothing here is scored.
    """
    print("\n=== judgement check sheet (not scored by this script) ===")
    seen = set()
    for row in rows:
        if row["case_id"] in seen:
            continue
        seen.add(row["case_id"])
        print("\n{}  [{}]".format(row["case_id"], row["family"]))
        print("  the key requires the record to say:")
        for item in row["must_record"]:
            print("    - {}".format(item))
        print("  the run recorded:")
        print("    " + json.dumps(row["detail"], ensure_ascii=False,
                                  indent=4).replace("\n", "\n    "))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--live", action="store_true",
                        help="use a real model instead of the scripted backend")
    parser.add_argument("--model", default=config.DEFAULT_MODEL)
    parser.add_argument("--api-key", default=os.environ.get("OPENROUTER_API_KEY"))
    parser.add_argument("--trials", type=int, default=1,
                        help="runs per case; negative cases want 3")
    parser.add_argument("--case", action="append", default=None,
                        help="run only this case id (repeatable)")
    parser.add_argument("--sequential", action="store_true",
                        help="scripted only: one action per turn instead of "
                             "batched parallel calls (D2c control arm)")
    parser.add_argument("--verbose", action="store_true",
                        help="print every model response and observation")
    parser.add_argument("--judgement-sheet", action="store_true",
                        help="print each record beside the key's must_record")
    parser.add_argument("--json", dest="json_out", default=None,
                        help="write the per-run rows to this file")
    args = parser.parse_args()

    expected_by_id = load_expected()
    claims = tools_module.load_table("claims")
    cases = [c for c in claims if c["claim_id"] in expected_by_id]
    if args.case:
        wanted = set(args.case)
        cases = [c for c in cases if c["claim_id"] in wanted]
        if not cases:
            raise SystemExit("no such case in the evaluation set: {}".format(
                ", ".join(sorted(wanted))))

    unlabelled = [c["claim_id"] for c in claims
                  if c["claim_id"] not in expected_by_id]
    if unlabelled:
        print("warning: {} claim(s) have no label in the answer key and were "
              "skipped: {}".format(len(unlabelled), ", ".join(unlabelled)),
              file=sys.stderr)

    if args.live:
        label = "live: " + args.model

        def backend_factory(claim):
            return LiveBackend(model=args.model, api_key=args.api_key)
    else:
        label = "scripted ({})".format(
            "sequential" if args.sequential else "parallel")

        def backend_factory(claim):
            return ScriptedBackend(
                scripts_A.script_for(claim["claim_id"],
                                     parallel=not args.sequential))

    # The gated action appends. Start each evaluation from an empty file so the
    # decision log is the log of this evaluation and not of every past one.
    open(config.DECISIONS_PATH, "w", encoding="utf-8").close()

    rows = run_evaluation(backend_factory, cases, expected_by_id,
                          trials=args.trials, verbose=args.verbose)
    passed, total = report(rows, label, args.trials)

    if args.judgement_sheet:
        print_judgement_sheet(rows)

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump(rows, fh, indent=2, ensure_ascii=False)
        print("\nper-run rows written to {}".format(args.json_out))

    print("decision letters appended to {}".format(config.DECISIONS_PATH))
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
