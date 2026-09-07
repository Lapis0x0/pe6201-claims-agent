# D2(c) — calling more than one tool in a turn, measured

## The dependency rule

From `scripts_A.py`'s canonical order (already the shape every trajectory,
shipped and added, follows):

1. `lookup_member_policy` — must run alone, first. Three business triggers
   (`policy_lapsed`, `outside_policy_dates`, `annual_limit_exceeded`) can end
   the run here, before anything else is known.
2. `check_duplicate` — must run alone, second (needs nothing `check_coverage`
   or `check_hospital` would add, but must happen before line pricing so a
   duplicate never wastes turns pricing lines it will never pay).
3. `check_hospital` + one `check_coverage` per line — **batched in one
   turn**. None of these calls depends on any other call's result; they
   only depend on step 1 having resolved the policy.
4. `get_preauthorisation`, once per line flagged `requires_preauth: yes` by
   step 3 — **cannot be batched with step 3**, because which lines need it
   is exactly what step 3 just told us. This is the one real dependency
   chain in Problem A's tool set (mirrors the brief's own point that a
   pair may go in parallel only when neither needs the other's output).
5. `issue_decision_letter` — the gated action, last, alone.

## Method: exact, not the closed-form estimate

The brief's `input ~= B*T + D*T(T-1)/2` assumes a uniform per-turn addition
`D`. We don't have to assume it — the scripted backend produces real text
for every turn, so `measure_parallel.py` replays **all 40 cases, both ways**,
and sums the actual character length of the message list sent to the
backend at every turn (the exact quantity the formula approximates). This is
more accurate than plugging in an assumed `D`, and it still costs nothing —
no network, no key.

For a visual sensitivity view, `generate_plots.py` uses the measured
current prefix `B = 2,165` tokens and the median inferred growth from the
parallel trajectories, `D = 176` tokens/turn. The resulting
`../figs/fig_d0_turn_token_growth.png` separates the repeated-prefix and
accumulated-history terms. Predicted input grows from 22,248 tokens at 8
turns to 55,760 at 16 turns: **2.51x**, not 2x. The exact replay remains the
D2(c) comparison; this curve isolates the turn trend so the nonlinear effect
is visible.

## Results, full 40-case set, 1 trial each

```
$ python3 measure_parallel.py
system prompt B: 8661 chars (~2165 tokens)

TOTAL across 40 cases: parallel 513,037 tokens, sequential 649,111 tokens,
saved 136,074 tokens (21.0%)
```

(`B` has grown twice since this file was first written — once for D5(b)'s
worked-example fix, once for the narrative/annual-limit prompt tightening —
and the absolute numbers below are re-measured each time from a live run of
`measure_parallel.py`, not hand-adjusted. The 21.0% saving is stable across
all three versions of the prompt because it's a ratio: the prefix grows
equally in both arms. `results/d2c_scripted_measured_current.json` always
holds the current numbers.)

**The consolidated comparison, aggregated over all 40 cases:**

| Metric | Sequential | Parallel | Saved |
|---|---|---|---|
| Turns (sum, 40 cases) | 254 | 202 | 52 (20.5%) |
| Tool calls (sum, 40 cases) | 214 | 214 | 0 — same trajectories, only batching differs |
| Input tokens | 649,111 | 513,037 | 136,074 (21.0%) |
| Output tokens | 19,619 | 19,503 | 116 (0.6%) |
| **Total tokens** | **668,730** | **532,540** | **136,190 (20.4%)** |
| Cost, cheap tier | \$0.0728 | \$0.0591 | \$0.0137 |
| Cost, mid tier | \$0.7276 | \$0.5910 | \$0.1365 |
| Pass rate | 100% (40/40) | 100% (40/40) | unchanged |
| Latency | N/A — scripted, no real network call | N/A | live latency needs D5(b) |

Tool calls are identical by construction (parallel calling regroups which
turn a call happens in, it never removes or adds a call) — the saving is
entirely in re-sent history, which is why turns and tokens drop while tool
calls don't.

Per-case savings range from **0%** (the 8 cases that stop early — 3 policy-
gate escalations at 2 calls, 2 duplicate escalations at 3 calls — where no
turn ever holds more than one call, so there is nothing to batch) to
**~51%** (`CLM-9000`, the five-line claim, where five independent
`check_coverage` calls collapse into one turn instead of five). The pattern
is exactly what the dependency rule predicts: **savings scale with how many
independent calls a claim's line count produces**, not with turn count
alone. `CLM-8842` (the brief's own worked example): 24,084 -> 16,067 input
tokens, 33.3% saved, 9 -> 6 turns.

Correctness: **100% pass rate both ways** (40/40 parallel, 40/40
sequential) — same trajectories, same decisions, only the batching differs.

## Reconciling with the brief's own worked example

The brief's Appendix A illustration for `CLM-8842` used illustrative
constants (`B=1,200`, `D=400`) and got 20,800 -> 9,600 tokens (54% saved).
Our measured numbers for the same case are 24,084 -> 16,067 (33.3% saved) —
directionally identical (parallel wins, by a lot), but a different
magnitude, for a fully explainable reason: our real system prompt is 2,165
tokens (six full descriptor contracts with size bounds, poka-yoke text, a
worked example for the gated write, and explicit narrative/arithmetic
guidance), well over the brief's illustrative 1,200, while our real
observations are
much smaller than the assumed 400 tokens each (`check_coverage` measures at
~36 tokens; see `config.TOOL_SPECS`). A bigger, more specific prompt prefix
and smaller, tighter observations shift the balance between the linear and
quadratic terms — which is itself evidence for D6: it says our tool
descriptors, not our observations, are the heavier part of *our* per-turn
cost, the opposite emphasis from the brief's illustrative numbers.

## Two honest limits (as the brief asks us to find)

1. **Parallel calls can raise cost when a call turns out to be
   unnecessary.** None of our 40 cases hit this, because `check_coverage`
   is always needed for every filed line regardless of order — but the
   effect is real in general: a sequential run can use turn *n*'s
   observation to decide turn *n+1* is unneeded, where a batched turn
   commits to all of them up front.
2. **Batching removes a decision point.** The model never sees line 1's
   coverage result before deciding whether to check line 2 — which is
   exactly why the four boundary/preauth cases (`CLM-9005`, `CLM-9010`,
   `CLM-9055`, etc.) still isolate `get_preauthorisation` into its own turn:
   that decision (which lines need it) is one we deliberately keep gated on
   seeing `check_coverage`'s answer first.

## Verification

```
$ python3 measure_parallel.py --json results/d2c_scripted_measured_current.json
$ python3 harness.py --json results/harness_scripted_default.json      # 40/40
$ python3 harness.py --sequential --json results/d2c_scripted_sequential.json  # 40/40
```

If `config.SYSTEM_PROMPT` changes, re-run all three — every absolute number
in this file (not the 21.0% ratio) depends on the current prompt size.
