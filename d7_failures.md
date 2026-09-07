# D7 — two reproduced failures

Both built as **"the working agent, minus X"** — never a separately written
bad agent — and both run on the scripted backend, free, reproducible by a
marker with no key. Both restorations set the deleted piece back to its
exact shipped value, so "Restored" below is not an approximation of the
working agent — it *is* the working agent, run again.

## Failure 1 (required) — a loop-control failure

**What was deleted**: `ClaimsAgent` already takes `max_repeats` as a
constructor argument (`agent.py`). Setting it to `999` instead of
`config.MAX_REPEATS` (2) is exactly equivalent to deleting the
action-de-duplication guard — nothing else about the agent changes.

**The script**: the model keeps re-issuing one identical
`get_preauthorisation` call, turn after turn, and never gives a Final
Answer.

**What failure occurred**: with the guard gone, the agent has no memory
that it already asked this question. It repeats the same call 15 times
and is only stopped by the step cap — a completely different, much
blunter guard than the one that should have caught it.

### Output table

| Metric | Working | Broken | Restored |
|---|---|---|---|
| Turns | 5 | **15** | 5 |
| Tool calls | 2 | **15** | 2 |
| Input tokens | 12,368 | **43,624** | 12,368 |
| Output tokens | 230 | 690 | 230 |
| Cost (cheap tier) | $0.00133 | **$0.00464** | $0.00133 |
| Decision | escalate | escalate | escalate |
| Pass (reaches a safe outcome) | **True** | **True** | **True** |
| Guard triggered | `repeated_action` | `step_cap_exceeded` | `repeated_action` |

**Working and Restored are identical** — restoring `max_repeats` to its
shipped default reproduces the working agent exactly, confirming the
"deletion" really was a clean, reversible toggle and not a stand-in for a
different bug.

**The important lesson, visible directly in this table**: `Pass` is
**`True` in all three columns.** The broken run still reaches `escalate`
— a defensible outcome — so pass rate alone reports no problem at all.
The only columns that reveal the failure are the instrumentation ones:
3.0x the turns, 3.5x the tokens, 3.5x the cost. This is exactly the
demo's own point: *the broken agent may still produce the correct answer
but use far more turns/tokens, so pass rate alone may not reveal the
failure.*

### Turn distribution across the real 40-case evaluation set

```
n=40  median=5  min=3  max=6  hit the 15-turn cap: 0/40
```

Not one of the 40 real cases comes anywhere near the step cap — the
farthest any legitimate run gets is 6 turns, 9 turns short of it. That gap
is what makes `MAX_STEPS = 15` a genuine safety net rather than something
ordinary claims bump into.

### Why the other two loop-control guards would not have caught it as well

| Guard | Would it have caught this? | Why / why not |
|---|---|---|
| **Action de-duplication** (the actual fix) | **Yes, at turn 5** | Recognises the exact failure signature — the same `(tool, args)` pair, repeated — directly and cheaply. |
| Step cap (15) | Eventually, at turn 15 | 3.0x later. Stops *any* non-terminating run, but only after the maximum possible cost has already been spent. |
| Budget ceiling (24 tool calls) | No, not before the step cap | One tool call per turn here, so 15 turns ≤ 24 tool calls — the ceiling never comes close to firing first. |

### The seven questions

- **What did you delete?** Action de-duplication (`max_repeats` set to 999
  instead of `config.MAX_REPEATS`).
- **What failure occurred?** The agent loops on one identical tool call
  for 15 turns with no memory that it already asked, and is only stopped
  by the step cap — a guard that exists for a different purpose and fires
  3x later than the correct one would have.
- **How did instrumentation reveal it?** Not by pass/fail — see the table
  above, `Pass` is `True` in every column. It's the turn/token/cost
  columns, already logged by `AgentResult` on every run (nothing new had
  to be built), that show a 3.0–3.5x blowup.
- **Which layer owns the fix? (prompt / tool interface / loop-control)**
  **Loop-control.** The fix is a code-level guard inside the agent's own
  turn loop, not a change to any tool or any prompt text.
- **Why are the other layers the wrong place to fix it?** A **prompt**
  instruction ("don't repeat yourself") would be re-paid every turn of
  every run forever, and a model can still ignore or misjudge it under a
  long context — exactly the D2(b)/D6 argument against paying for
  reliability in prose. The **tool interface** (`get_preauthorisation`
  itself) has nothing to fix — the tool did exactly what it was asked,
  correctly, 15 times; the defect is entirely in whether the *loop*
  remembers it already asked, which only the loop can own.
- **Did the fix introduce regressions?** No. `python3 harness.py` is
  still 40/40 with `max_repeats` at its normal default (see Verification)
  — restoring the guard costs nothing, because the turn distribution
  above shows no legitimate case ever gets within 9 turns of triggering
  it.
- **Did pass rate recover after restoration?** Yes — 40/40, unchanged
  from before this failure was ever introduced, because the deletion only
  touched a constructor argument passed to a standalone script, never
  `config.MAX_REPEATS` itself.

## Failure 2 — a different layer: the tool interface, not loop control

**What was deleted**: `check_duplicate`'s real, shipped match requires
four facts — member, hospital, date of service, and line items
(`_line_key(prior["lines"]) == wanted`). `BrokenDuplicateMatch` in
`failure2_interface.py` subclasses `ClaimsTools` and overrides
`check_duplicate` to drop the fourth. This is not hypothetical: it is
exactly the failure mode `scripts_A.py`'s own shipped note for `CLM-8960`
already names — *"it is ALSO the case that forces the lines comparison:
an agent matching duplicates on member + hospital + date alone will
wrongly escalate this one."* `CLM-8960` (a genuine 4-line claim) shares
member, hospital and date with `CLM-8726` in `decided_claims` — a
genuine, *different*, 1-line prior claim on the same day — and the
weakened interface reports a false `MATCH`.

### Output table

| Metric | Working | Broken | Restored |
|---|---|---|---|
| Turns | 5 | **4** | 5 |
| Tool calls | 8 | **3** | 8 |
| Input tokens | 13,093 | **9,697** | 13,093 |
| Output tokens | 745 | 262 | 745 |
| Cost (cheap tier) | $0.00161 | **$0.00108** | $0.00161 |
| Decision | approve_in_principle | escalate | approve_in_principle |
| Pass (vs D4's real answer key) | **True** | **False** | **True** |
| Guard triggered | none | none | none |

**The uncomfortable finding, opposite of Failure 1**: here the *broken*
run is cheaper on every instrumentation signal (fewer turns, fewer tool
calls, fewer tokens, lower cost) — because escalating early skips pricing
the four lines the correct answer has to price. Unlike Failure 1, turns
and cost do not flag this failure at all; the run looks efficient. **The
only column that catches it is `Pass`**, checked against D4's real answer
key (`expected_outcomes_A.json`: `CLM-8960` → `approve_in_principle`,
`approved_total: 1990`) — which is exactly why D4's code check exists,
and exactly why "the run finished quickly" is not evidence of
correctness. `Guard triggered` is `none` in every column: no loop-control
or gate guard has anything to say about a tool that returns
well-formed-but-wrong data.

### The seven questions

- **What did you delete?** The fourth match criterion (line items) inside
  `check_duplicate`'s comparison — `BrokenDuplicateMatch` matches on
  member + hospital + date alone.
- **What failure occurred?** A genuine, payable 4-line claim
  (`CLM-8960`) collides with an unrelated 1-line prior claim that happens
  to share the same member, hospital and date, and is wrongly escalated
  as a duplicate. The model's reasoning from the tool's answer is sound —
  the tool lied to it.
- **How did instrumentation reveal it?** It didn't — that's the point.
  Turns, tool calls and cost all look *better* for the broken run (see
  table). The failure is only visible by checking `Pass` against D4's
  answer key, not against any run-time signal.
- **Which layer owns the fix? (prompt / tool interface / loop-control)**
  **Tool interface** — `check_duplicate`'s own comparison logic.
- **Why are the other layers the wrong place to fix it?** A **prompt**
  sentence telling the model to "check line items carefully before
  concluding a duplicate" would be re-paid on every turn of every run
  forever, and a model could still misread or deprioritise it under a
  long enough context. **Loop-control** has nothing to say here either —
  the run didn't loop, spin, or repeat anything; it took a clean,
  efficient, wrong path once, so no turn/budget/repeat guard was ever
  going to fire. Requiring all four facts inside `check_duplicate`'s own
  comparison makes the false-positive class of error **structurally
  impossible** rather than merely discouraged.
- **Did the fix introduce regressions?** No. `python3 harness.py` is
  still 40/40 restored (see Verification) — `check_duplicate`'s real
  4-fact comparison is the shipped, unmodified code; nothing about
  restoring it changes behaviour on any of the other 39 cases, none of
  which depend on the dropped fact.
- **Did pass rate recover after restoration?** Yes — `CLM-8960` passes
  (`approve_in_principle`, `approved_total: 1990`, matching D4's answer
  key exactly) once `check_duplicate` is back to comparing all four
  facts, and the full 40-case set remains 40/40.

## Verification

```
$ python3 failure1_loop.py       # turn distribution, Working/Broken/Restored, both caps compared
$ python3 failure2_interface.py  # Working/Broken/Restored, tokens/cost/pass now included
$ python3 harness.py             # unaffected: 40/40
$ python3 guardrail_checklist.py # unaffected: 12/12
```
