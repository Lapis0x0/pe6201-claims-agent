# PE6201 A2 — Health-Insurance Claim First Response Agent

**Course:** PE6201 Emerging AI Technologies  
**Programme:** MSc Enterprise Artificial Intelligence, Nanyang Technological University  
**Assessment:** A2 — Applied AI System  
**Problem:** A — Health-Insurance Claim First Response

## Overview

This project implements a **single-agent ReAct system** for health-insurance claim first-response processing.

The agent receives a claim, dynamically retrieves the required information using tools, evaluates the claim against policy, coverage, pre-authorisation, hospital and supporting-document information, and produces one of three outcomes:

- **Approve in principle**
- **Request a specific missing document**
- **Escalate** the claim to a human assessor

The system follows a tool-using **Reason → Act → Observe → Repeat → Final** loop, with explicit guardrails around the gated decision action.

## Problem A — Health-Insurance Claim First Response

The agent works with claim, member, policy, coverage, pre-authorisation, hospital and document information to determine the appropriate first response for a health-insurance claim.

The core workflow is:

**Claim → Member & Policy → Coverage Checks → Pre-authorisation / Hospital / Documents → Approve / Request / Escalate**

The decision-letter action is simulated locally and does **not** send a real letter or modify any live insurance system.

## Team

**Team ID:** B-9  
**Section:** B

| # | Team Member |
|---|---|
| 1 | JIANG DONG |
| 2 | LIU WEIQI |
| 3 | NIU DUOER |
| 4 | SHI ZHIYUN |
| 5 | UBAIDULLA ASMITHA |
| 6 | XU LIANGJUAN |
## Repository layout

Runnable code, fixture data, and results stay at the repository root so
every command in "Running it" below works straight after a clone. The
write-ups for each deliverable live in `docs/`, and every committed figure
lives in `figs/` — both are referenced by path in the table below.

| File | What it is |
|---|---|
| `config.py` | Paths, the decision and trigger vocabularies, the guardrail caps, the tool descriptors, and the system prompt. The prompt's tool list is rendered from `TOOL_SPECS`, so the prompt cannot drift from the tool layer. |
| `tools.py` | The tool layer. Six tools over the local fixture data (a seventh, `get_claim`, was cut under D2(a) — see `docs/d2_tool_analysis.md`); each returns a formatted observation string. `issue_decision_letter` is the gated action and carries its own gate. |
| `agent.py` | The ReAct loop and the code-level guardrails. Also a CLI for running one claim with its full trace. |
| `backend.py` | `ScriptedBackend` (default, no key, no cost) and `LiveBackend` (OpenRouter, OpenAI-compatible). |
| `scripts_A.py` | The recorded trajectories the scripted backend replays, one per shipped case. |
| `harness.py` | The evaluation harness: runs the set, applies the code check, prints the judgement sheet. |
| `data_A/`, `expected_outcomes_A.json`, `make_fixtures_A.py`, `check_my_data.py` | The fixture data, the answer key, the generator, and the data checker, as shipped. |
| `docs/d0_justification.md` | D0: why this problem needs an agent. |
| `generate_plots.py`, `figs/fig_d0_class4_bill_test.png`, `figs/fig_d0_turn_token_growth.png` | One generator for the standalone supplementary figures: completed-task cost, turn sensitivity, and the two historical D5 diagnostics. The primary D2-D7 figures remain in the analysis notebook. |
| `docs/d1_sample_traces.md` | D1: one trace per outcome (approve/ask/escalate) and a fully instrumented decision record (turns, tool calls, tokens, cost, runtime, guardrails fired, evidence trace). |
| `docs/d2_tool_analysis.md` | D2(a): the tool set scored against the three questions, and the evidence for cutting `get_claim`. |
| `docs/d2b_descriptor_rewrite.md`, `descriptors_v1.py`, `measure_d2b.py` | D2(b) descriptor: the six-field descriptors, four poka-yoke moves, actual observation-return size, the 12/12-vs-12/12 guardrail control, and the v1-vs-v2 live comparison on `openai/gpt-4o-mini` (66.7% v2 vs 64.4% v1, trial-level, current 50-case set). |
| `docs/d2b_return_shape.md`, `measure_return_shape.py` | D2(b) return shape: `check_coverage`'s actual return value, prose (v1) vs typed JSON (v2), descriptor pinned at v2 in both arms — 74.4% v2 vs 70.0% v1, trial-level, current 50-case set. |
| `docs/d4_case_notes.md`, `docs/d4_judgement_checks.md`, `docs/judgement_check_prompt.md` | D4: the 50-case evaluation set, run arithmetic, code checks, and two independent live-record judgement-check passes across two models (2/20 combined; evidence-detail gaps documented). |
| `docs/d2c_measurement.md`, `measure_parallel.py` | D2(c): the dependency rule, and an exact (not approximated) parallel-vs-sequential token measurement over all 50 cases. |
| `docs/d3a_autonomy.md` | D3(a): the autonomy setting (suggest/confirm/act), made into real enforced behaviour rather than a descriptive label, and why `confirm` is the shipped default. |
| `docs/d3b_guardrail_checklist.md`, `guardrail_checklist.py` | D3(b): the 12-case guardrail checklist (step cap, budget ceiling, dedup, gate x3 incl. operator approval, invalid arguments, 3 hostile-narrative shapes), scripted and free. |
| `docs/d6_notes.md`, `d6_cost_model.py` | D6: the three-layer cost model, all four levers measured before/after, a sensitivity range in place of an unmeasured success rate, and the break-even mechanism. |
| `docs/d7_failures.md`, `failure1_loop.py`, `failure2_interface.py` | D7: two reproduced failures, each built as "the working agent, minus X." Failure 1 (required): de-duplication removed, a loop runs to the step cap; 3.0x turns, 3.6x cost, fixed by restoring the guard. Failure 2 (interface layer): `check_duplicate`'s match weakened from 4 facts to 3, producing a confident, wrong, and *cheaper*-looking escalation of a genuine claim. |
| `demo_loop_failure.py` | A narrated, presentation-friendly run of Failure 1 — same evidence as `failure1_loop.py`, formatted for the 5-minute demo video. `python3 demo_loop_failure.py`, no key needed. |
| `A2_tour.ipynb` | Optional — a narrated, one-case (`CLM-8842`) walkthrough of the whole system, cell by cell, mirroring the professor's own scaffold tour notebook but against our modules and our 50-case data. Good for onboarding teammates and for the demo video; not what a marker runs. |
| `results/` | Committed run outputs (`--json` exports) the `docs/*.md` write-ups cite numbers from — see `results/README.md`. Everything there is free to regenerate except the one live smoke-test file. |
| `A2_analysis.ipynb` | Optional — not a submission requirement (see D5(a): `harness.py` is what a marker runs). Imports the modules above to run and plot D2(a)/(b)/(c), D3(b), D4, D6, D7 and D5(b) in one place. Figures are saved to `figs/*.png` for the report — the notebook's own `savefig` cells write there directly. |
| `docs/d5a_reproducibility.md` | D5(a): proof the scripted backend is deterministic — two clean runs, diffed, identical except wall-clock timing. |
| `docs/d5b_live_battery.md` | D5(b): the live battery across five models spanning five families and two-plus price tiers (`gpt-4o-mini`, `gemini-2.5-flash`, `deepseek-v4-flash`, `llama-3.1-8b-instruct`, `qwen-2.5-7b-instruct`) — pass rate, turns, tokens, cost and latency compared side by side, plus a failure-by-family matrix. |

## Running it

The default backend is scripted. No API key, no network, no cost.

```bash
python3 harness.py                  # the whole evaluation set
python3 harness.py --sequential     # same trajectories, one action per turn
python3 harness.py --case CLM-8894 --verbose
python3 harness.py --judgement-sheet
python3 agent.py CLM-8842           # one claim, full trace
python3 measure_d2b.py              # D2(b) descriptor zero-cost control measurements
python3 measure_return_shape.py     # D2(b) return-shape zero-cost control measurements
python3 verify_submission.py         # all zero-cost checks plus evidence validation
python3 generate_plots.py             # reproduce all standalone figures
```

To run a real model, install `openai` and pass a key:

```bash
pip install -r requirements.txt
python3 harness.py --live --model openai/gpt-4o-mini --api-key $OPENROUTER_API_KEY
```

Check the fixture data after any change to it:

```bash
python3 check_my_data.py
```

## The decision loop

The model chooses the next action at runtime from the observations it receives.
The prompt supplies a dependency rule rather than a fixed workflow: establish
policy eligibility first, stop early when evidence already decides the case,
batch independent checks, and never call a dependent tool before its arguments
have been observed. Typical successful trajectories therefore look like this:

1. `lookup_member_policy` — a lapsed policy, a date of service outside the
   policy window, or a claim total above the remaining limit each escalate
   immediately. None of them are worth pricing line by line.
2. `check_duplicate` — matched on all four of member, hospital, date of service
   and line items. Three of the four is not a duplicate.
3. `check_hospital` and one `check_coverage` per line, issued together: they do
   not depend on one another.
4. `get_preauthorisation`, only for the lines whose coverage check returned
   `requires_preauth: yes`, and always against the date of service.
5. `issue_decision_letter`, then the final answer.

Step 4 depends on step 3, which is why it is a separate turn. That is the
dependency rule for parallel calls: batch what is independent, never batch a
call whose arguments come from a result you have not seen.

## Guardrails

In code, in `agent.py` and `tools.check_decision_gate`, not in the prompt:

- **Step cap** — `MAX_STEPS` model turns.
- **Budget ceiling** — `MAX_TOOL_CALLS` tool invocations, checked before they
  are spent. This is the resource budget for the action that expands later
  prompts; combined with `MAX_STEPS` and the backend's output-token cap, it
  bounds the run while still allowing multi-action turns.
- **Action de-duplication** — the same tool with the same arguments is refused
  after `MAX_REPEATS` attempts. The records do not change during a run.
- **Autonomy gate** — the loop will not accept a final answer until
  `issue_decision_letter` has been recorded, and the gate refuses that write
  unless the policy was looked up in this run, the decision is one of the three
  allowed values, the detail carries the fields that decision requires, and no
  letter has already been issued.
- **Untrusted narrative** — the member narrative is fenced and labelled in the
  prompt. Tool results reach the model only in an `Observation` line written by
  the loop, so text in a claim cannot present itself as one.

When a guardrail fires the run escalates to a human claims assessor with a
loop-control trigger. It does not crash and it does not guess.

## What the gated action does

`issue_decision_letter` appends one JSON record per decision to
`decisions.jsonl` in this directory. It sends nothing, and it touches no live
system. The file is git-ignored: it is the output of a run, not a source file.
Each record carries the decision and its evidence trail, autonomy setting,
gate/approval status, timestamp, turn count and cost — see
`docs/d1_sample_traces.md` for the full shape.
