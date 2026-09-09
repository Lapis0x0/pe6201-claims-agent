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
# PRICE_PER_MILLION / cost_usd() live in config.py, the single source of
# truth agent.py's gated-action record (D1's decisions.jsonl "cost_usd"
# field) and this harness both read. Re-exported here so existing imports
# (`from harness import PRICE_PER_MILLION`, e.g. d6_cost_model.py) keep
# working unchanged.
from config import PRICE_PER_MILLION, cost_usd


def load_expected(path=config.EXPECTED_OUTCOMES_PATH):
    with open(path, encoding="utf-8") as fh:
        return {row["case_id"]: row for row in json.load(fh)}


def check(result, expected):
    """The code check. Returns (passed, reason).

    Every field checked here comes from a fixed vocabulary or a number - the
    FAQ's own definition of a code check ("the decision field equals the
    expected value, the single trigger matches, a required tool appears in
    the trace, the gated action fired exactly once"). Prose (missing_document
    itself, the reason narrative) stays a judgement check - see
    print_judgement_sheet.
    """
    if result.decision != expected["expected_decision"]:
        return False, "expected {}, got {}".format(
            expected["expected_decision"], result.decision)
    if not result.letter_issued:
        return False, "the gated action never fired"
    wanted_trigger = expected.get("trigger")
    if wanted_trigger:
        got = result.detail.get("trigger")
        if got != wanted_trigger:
            return False, "expected trigger {}, got {}".format(
                wanted_trigger, got)
    wanted_line = expected.get("expected_line")
    if wanted_line:
        got = result.detail.get("line")
        if got != wanted_line:
            return False, "expected missing-document line {}, got {}".format(
                wanted_line, got)
    wanted_approved = expected.get("expected_approved_total")
    if wanted_approved is not None:
        for field, wanted in (("approved_total", wanted_approved),
                              ("refused_total",
                               expected["expected_refused_total"])):
            got = result.detail.get(field)
            if got != wanted:
                return False, "expected {} {}, got {}".format(
                    field, wanted, got)
    return True, ""


def run_evaluation(backend_factory, cases, expected_by_id, trials=1,
                   verbose=False, prompt_overrides=None, negative_trials=None,
                   model=None, return_shape_version="v1"):
    """Run every case its own number of times, and score each run.

    Ordinary cases get `trials`. Negative cases (expected_decision !=
    approve_in_principle) get `negative_trials` if given, else `trials` too -
    the brief's arithmetic wants negative cases run 3x per model since they
    are the ones that flip between runs; on a live model this is the
    difference between paying for 80 runs and paying for 56.
    """
    rows = []
    for claim in cases:
        case_id = claim["claim_id"]
        expected = expected_by_id[case_id]
        is_negative = expected["expected_decision"] != "approve_in_principle"
        n_trials = negative_trials if (is_negative and negative_trials) else trials
        for trial in range(1, n_trials + 1):
            claim_tools = tools_module.ClaimsTools(
                claim, return_shape_version=return_shape_version)
            agent = ClaimsAgent(backend_factory(claim), claim,
                                claim_tools=claim_tools, verbose=verbose,
                                prompt_overrides=prompt_overrides)
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
                "cached_tokens": result.cached_tokens,
                "reasoning_tokens": result.reasoning_tokens,
                "runtime_seconds": result.runtime_seconds,
                "guardrails_fired": result.guardrails_fired,
                "cost_usd": (0.0 if not (result.prompt_tokens or
                                        result.completion_tokens)
                            else cost_usd(model, result.prompt_tokens,
                                          result.completion_tokens)),
            })
    return rows


def report(rows, label, trials, negative_trials=None):
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
    n_cases = len(set(r["case_id"] for r in rows))
    print("-" * 92)
    print("backend: {}".format(label))
    if negative_trials and negative_trials != trials:
        n_ordinary = sum(1 for r in rows
                         if r["expected"] == "approve_in_principle"
                         and r["trial"] == 1)
        n_negative = n_cases - n_ordinary
        print("pass rate: {:.1%}  ({}/{} runs; {} ordinary cases x {} "
              "trial{} + {} negative cases x {} trials)".format(
                  passed / total if total else 0.0, passed, total,
                  n_ordinary, trials, "" if trials == 1 else "s",
                  n_negative, negative_trials))
    else:
        print("pass rate: {:.1%}  ({}/{} runs; {} cases x {} "
              "trial{})".format(passed / total if total else 0.0, passed,
                                total, n_cases, trials,
                                "" if trials == 1 else "s"))

    steps = [r["steps"] for r in rows]
    if steps:
        median = sorted(steps)[len(steps) // 2]
        print("turns: median {}, average {:.1f}, min {}, max {}".format(
            median, sum(steps) / len(steps), min(steps), max(steps)))
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


def print_d4_summary(rows):
    """D4's own results table and metrics: pass rate by family, the
    negative/ordinary split, a decision confusion count, and one row per
    case (not per trial) with the code-check verdict and a placeholder for
    the judgement verdict, which this script never grades itself.
    """
    by_case = {}
    for row in rows:
        by_case.setdefault(row["case_id"], []).append(row)

    judgement_path = os.path.join(
        os.path.dirname(__file__), "results", "judgement_checks.json"
    )
    judgement_by_case = {}
    if os.path.exists(judgement_path):
        with open(judgement_path, encoding="utf-8") as fh:
            judgement_by_case = {
                item["case_id"]: item["verdict"]
                for item in json.load(fh)["results"]
            }

    print("\n=== D4 results table (one row per case, {} trials each on "
          "average) ===".format(round(len(rows) / len(by_case), 1)))
    print("{:<10} {:<30} {:<21} {:<21} {:<28} {:<10} {:<10} {}".format(
        "case", "family", "expected", "actual", "trigger", "code check",
        "live judge", "code result"))
    print("-" * 145)
    case_passed = 0
    for case_id, case_rows in by_case.items():
        all_pass = all(r["passed"] for r in case_rows)
        case_passed += all_pass
        one = case_rows[0]
        print("{:<10} {:<30} {:<21} {:<21} {:<28} {:<10} {:<10} {}".format(
            case_id, one["family"][:30], one["expected"], one["actual"],
            one["actual_trigger"] or "-",
            "PASS" if all_pass else "FAIL",
            judgement_by_case.get(case_id, "not selected"),
            "PASS" if all_pass else "FAIL"))
    print("-" * 145)
    print("supplementary strict case-consistency rate: {}/{} ({:.1%}) - "
          "a negative case counts only if all three trials pass; this is "
          "not the FAQ-defined primary pass rate above".format(case_passed, len(by_case),
                          case_passed / len(by_case) if by_case else 0.0))

    print("\npass rate by family:")
    fam_total = Counter()
    fam_passed = Counter()
    for case_id, case_rows in by_case.items():
        fam = case_rows[0]["family"]
        fam_total[fam] += 1
        fam_passed[fam] += all(r["passed"] for r in case_rows)
    for fam in sorted(fam_total):
        print("  {:<45} {}/{}".format(fam, fam_passed[fam], fam_total[fam]))

    ordinary = [r for case_rows in by_case.values()
               for r in [case_rows[0]] if r["expected"] == "approve_in_principle"]
    negative = [r for case_rows in by_case.values()
               for r in [case_rows[0]] if r["expected"] != "approve_in_principle"]
    ord_pass = sum(all(r["passed"] for r in by_case[r0["case_id"]])
                  for r0 in ordinary)
    neg_pass = sum(all(r["passed"] for r in by_case[r0["case_id"]])
                  for r0 in negative)
    print("\nordinary-case pass rate: {}/{} ({:.1%})".format(
        ord_pass, len(ordinary), ord_pass / len(ordinary) if ordinary else 0))
    print("negative-case pass rate: {}/{} ({:.1%})".format(
        neg_pass, len(negative), neg_pass / len(negative) if negative else 0))

    confusion = Counter(
        (case_rows[0]["expected"], case_rows[0]["actual"])
        for case_rows in by_case.values()
        if case_rows[0]["expected"] != case_rows[0]["actual"]
    )
    print("\ndecision confusion (expected -> actual, mismatches only):")
    print("  none" if not confusion else "")
    for (expected, actual), count in confusion.items():
        print("  {} -> {}: {}".format(expected, actual, count))


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
                        default=(config.BACKEND == "live"),
                        help="use a real model instead of the scripted "
                             "backend. Defaults to config.BACKEND "
                             "('scripted'), the one switch in the brief's "
                             "BACKEND/MODEL/BASE_URL block.")
    parser.add_argument("--model", default=config.DEFAULT_MODEL)
    parser.add_argument("--api-key", default=os.environ.get("OPENROUTER_API_KEY"))
    parser.add_argument("--trials", type=int, default=1,
                        help="runs per ordinary case")
    parser.add_argument("--negative-trials", type=int, default=3,
                        help="runs per negative case (they flip between "
                             "runs; the brief's arithmetic wants 3). Pass "
                             "--negative-trials 1 to match --trials for a "
                             "quick/cheap smoke test.")
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
    parser.add_argument("--descriptor-version", choices=["v1", "v2"],
                        default="v2",
                        help="D2(b) control arm: v1 swaps in the "
                             "deliberately worse check_coverage descriptor "
                             "from descriptors_v1.py. Only affects --live "
                             "runs; the scripted backend never reads the "
                             "prompt.")
    parser.add_argument("--return-shape-version", choices=["v1", "v2"],
                        default="v1",
                        help="D2(b) return-shape control arm: v2 swaps "
                             "check_coverage's actual return value from a "
                             "prose sentence to typed JSON, holding the "
                             "descriptor fixed at v2. Only affects --live "
                             "runs; the scripted backend's expected "
                             "trajectories assume v1.")
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

    prompt_overrides = None
    if args.descriptor_version == "v1":
        import descriptors_v1
        prompt_overrides = descriptors_v1.OVERRIDES

    if args.live:
        label = "live: {} (descriptors {}, return-shape {})".format(
            args.model, args.descriptor_version, args.return_shape_version)

        def backend_factory(claim):
            return LiveBackend(model=args.model, api_key=args.api_key)

        # Provenance: the exact rendered prompt this run used, fingerprinted
        # so it is independently checkable rather than only asserted in
        # prose (results/manifest.json's prompt_sha256 for each canonical
        # run is this same hash, computed the same way).
        import hashlib
        prompt_text = config.build_system_prompt(prompt_overrides)
        prompt_hash = hashlib.sha256(prompt_text.encode()).hexdigest()
        print("prompt sha256 ({} chars): {}".format(
            len(prompt_text), prompt_hash))
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
                          trials=args.trials, verbose=args.verbose,
                          prompt_overrides=prompt_overrides,
                          negative_trials=args.negative_trials,
                          model=args.model if args.live else None,
                          return_shape_version=args.return_shape_version)
    passed, total = report(rows, label, args.trials, args.negative_trials)
    print_d4_summary(rows)

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
