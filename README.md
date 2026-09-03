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

| File | What it is |
|---|---|
| `config.py` | Paths, the decision and trigger vocabularies, the guardrail caps, the tool descriptors, and the system prompt. The prompt's tool list is rendered from `TOOL_SPECS`, so the prompt cannot drift from the tool layer. |
| `tools.py` | The tool layer. Seven tools over the local fixture data; each returns a formatted observation string. `issue_decision_letter` is the gated action and carries its own gate. |
| `agent.py` | The ReAct loop and the code-level guardrails. Also a CLI for running one claim with its full trace. |
| `backend.py` | `ScriptedBackend` (default, no key, no cost) and `LiveBackend` (OpenRouter, OpenAI-compatible). |
| `scripts_A.py` | The recorded trajectories the scripted backend replays, one per shipped case. |
| `harness.py` | The evaluation harness: runs the set, applies the code check, prints the judgement sheet. |
| `data_A/`, `expected_outcomes_A.json`, `make_fixtures_A.py`, `check_my_data.py` | The fixture data, the answer key, the generator, and the data checker, as shipped. |
| `d0_justification.md` | D0: why this problem needs an agent. |

## Running it

The default backend is scripted. No API key, no network, no cost.

```bash
python3 harness.py                  # the whole evaluation set
python3 harness.py --sequential     # same trajectories, one action per turn
python3 harness.py --case CLM-8894 --verbose
python3 harness.py --judgement-sheet
python3 agent.py CLM-8842           # one claim, full trace
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

The agent works a claim in a fixed order, and the order is the point: each of
the first two steps can end the run before any line item is priced.

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
  are spent.
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
