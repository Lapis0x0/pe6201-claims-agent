# D6 — the cost-to-serve model

The separate completed-task diagnostic (`C_run / p`) is reported in
`d0_justification.md` and plotted in `../figs/fig_d0_class4_bill_test.png`. This D6
section uses the Class 5 escalation formula required by the A2 FAQ; the two
models are not combined.

Uses the Class 5 three-layer model, computed in `d6_cost_model.py` directly
from this repository's committed result files (`results/d5b_live_*.json`,
`results/d2b_live_*.json`, `measure_parallel.py`) — every number below is
measured, not estimated, now that all five D5(b) models plus the D2(b)
v1/v2 pair have real live data.

## Problem A's given inputs (Appendix A)

- Volume: **8,000 claims/month**
- Failure cost: claims assessor at **$38/hour**, **12 minutes** per
  escalated claim = **$7.60**

## The three shipping caps

| Cap | Shipped value | Evidence and behaviour at the boundary |
|---|---:|---|
| Step cap | **15 model turns/run** | The 50-case parallel run had median 5 and worst legitimate 6 turns (unchanged from the 40-case set the cap was first derived from). Fifteen is 2.5x that observed maximum; D7 reproduces a loop that stops loudly at this cap. |
| Budget ceiling | **24 tool calls/run** | This is an action/resource budget, not a dollar estimate. Tool calls create observations that are appended to history and re-sent on later turns, so limiting calls directly bounds the agent-controlled source of token growth. The loop checks the whole proposed batch before executing it; a batch that would cross 24 is rejected atomically and escalated. Together with the 15-turn cap and the live backend's per-response output cap, it bounds both tool-driven input growth and model output. G2 reproduces the boundary at zero cost. |
| Monthly limit per user | **US$1.00 per policy member/month** | At the cheapest-overall model's measured cost of **$0.0857 expected cost/claim** (`deepseek-v4-flash` — see the D6 ranking below), the cap permits roughly 11–12 average claims before routing further ones to the existing human process. This is a stated operating-policy assumption; persistent user-account storage is outside A2's file-based prototype. |

`MAX_TOOL_CALLS` is therefore intentionally named the budget ceiling in the
code: it budgets the scarce action that expands later prompts. It is separate
from `MAX_STEPS`, fires on a different scripted case, and is checked before
the calls are spent rather than after the bill has already grown.

**Version status: current as of 2026-09-09.** All five D5(b) models plus
the D2(b) v1/v2 pair are re-run against the final 50-case D4 set (90
trials each). Re-measurement moved more than numbers: `deepseek-v4-flash`
overtook `gemini-2.5-flash` for first place (91.25% -> 98.9%, vs
`gemini`'s 96.25% -> 93.3%), which is why the break-even section below
now targets `deepseek`, not `gemini` — `d6_cost_model.py` picks the
cheapest-overall model dynamically rather than hand-naming one, precisely
so this kind of ranking change does not go stale silently.

`gpt-4o-mini`'s v1-vs-v2 re-run measures the deliberately-worse v1 control
`descriptors_v1.py` ships against the brief's spec — see
`d2b_descriptor_rewrite.md` for the full descriptor comparison. v2 wins by
+2.3pp (66.7% vs 64.4%). The numbers below use v2, D6's baseline
throughout.

## Layer 1 — AI variable cost

`input_tokens × input_price + output_tokens × output_price`, measured per
model from its own live battery (real OpenRouter usage, all five models
and both prompt versions at 90 trials against the current 50-case set):

| Model | Input tok/run | Output tok/run | L1 (variable)/run |
|---|---|---|---|
| gemini-2.5-flash | 14,421 | 532 | $0.00566 |
| deepseek-v4-flash | 12,976 | 1,088 | $0.00122 |
| gpt-4o-mini | 18,721 | 546 | $0.00314 |
| qwen-2.5-7b-instruct | 19,055 | 647 | $0.00203 |
| llama-3.1-8b-instruct | 16,341 | 833 | $0.00088 |

## Layer 2 — expected fallback cost

`(1 - success_rate) × $7.60`, using the FAQ-defined trial-level pass rate
(`passing trials / total trials`) from each real D5(b) battery:

| Model | p (measured) | L2 (fallback)/task |
|---|---|---|
| deepseek-v4-flash | 89/90 (98.89%) | $0.0844 |
| gemini-2.5-flash | 84/90 (93.33%) | $0.5067 |
| gpt-4o-mini | 60/90 (66.67%) | $2.5333 |
| qwen-2.5-7b-instruct | 49/90 (54.44%) | $3.4622 |
| llama-3.1-8b-instruct | 33/90 (36.67%) | $4.8133 |

## Layer 3 — fixed monthly cost, stated assumption

No server: fixture files and the scripted harness cost nothing to run. A
monthly live re-run of the evaluation battery for regression monitoring is
part of the recurring cost here, but not the whole of it: at the cheapest
measured model (`deepseek-v4-flash`, L1 ~$0.0012/run), 50 cases costs
about $0.06/month, nowhere near the stated figure. **$5.00/month** is
better read as a monitoring/maintenance *allowance* the battery re-run is
drawn from — covering the re-run plus general upkeep — not a claim that
the re-run alone costs $5. This is a stated assumption, not a
measurement; the brief does not fix a figure for this layer.

## Caching and reasoning — neither is in this baseline, and here is why

**Caching: not modelled, not measured for the five batteries already run.**
Layer 1 above is the plain baseline the brief asks for — input and output
tokens at list price, no adjustment. We did not deliberately enable prompt
caching on any provider. At the time of the five D5(b) batteries and the
D2(b) v1/v2 pair, `backend.py`'s `LiveBackend.generate()` only captured
the top-level `usage.prompt_tokens`/`completion_tokens` totals, not a
`prompt_tokens_details.cached_tokens` breakdown — so if a provider applied
automatic caching behind the scenes on any of those runs, our instrumentation
could not have detected or reported it at the time. `backend.py` now
captures `cached_tokens` and `reasoning_tokens` when a provider returns
them (propagated through `AgentResult` and `harness.py`'s `--json` output
as of this fix), so this gap does not recur on any future run — but it is
real for the results already committed, disclosed here rather than left
implicit: our reported Layer-1 costs for the five batteries are the
uncached baseline the brief asks for as the default, but we cannot rule
out silent caching having occurred at the provider level on those specific
runs.

**Reasoning: not used, and the measured output-token counts support that.**
None of our five models are marketed as reasoning models — no o-series,
no GPT-5, no Claude extended-thinking, no `deepseek-reasoner` (we ran
`deepseek/deepseek-v4-flash`, the chat variant). The one model in this
battery with a plausible hidden-thinking mode is `gemini-2.5-flash`, whose
"thinking" behaviour is model-dependent; we did not explicitly set a
`reasoning` object to disable it. The brief's own diagnostic — "if output
per turn jumps by an order of magnitude, that is what happened" — gives a
way to check this after the fact from data already measured: per-turn
output across all five models (output tokens/run ÷ median turns) is
532÷5≈106 (gemini), 1,088÷5≈218 (deepseek), 546÷8≈68 (gpt-4o-mini),
647÷7≈92 (qwen), 833÷6≈139 (llama) — all within roughly a 3x band of each
other, not the 5-10x spike the brief describes as the signature of hidden
reasoning tokens. This is evidence against reasoning contamination, not
proof of its absence for these five already-committed batteries — the
same instrumentation gap above means we could not directly read a
`reasoning_tokens` field at the time to confirm zero; the field is
captured now for any run going forward.

## D6 outputs — all five models, ranked by total cost/task

| Model | Cost/task (L1) | Fallback cost/task (L2) | Total expected cost/task | Monthly @ 8,000 |
|---|---|---|---|---|
| **deepseek-v4-flash** | $0.0012 | $0.0844 | **$0.0857** | **$690** |
| gemini-2.5-flash | $0.0057 | $0.5067 | $0.5123 | $4,104 |
| gpt-4o-mini | $0.0031 | $2.5333 | $2.5365 | $20,297 |
| qwen-2.5-7b-instruct | $0.0020 | $3.4622 | $3.4643 | $27,719 |
| llama-3.1-8b-instruct | $0.0009 | $4.8133 | $4.8142 | $38,519 |

**This ranking inverts raw token price for the weakest model, and breaks
it entirely for the strongest.** `llama-3.1-8b-instruct` is the *cheapest*
model by token cost (L1 = $0.00088/run) and the *most expensive* overall
(~55.8x `deepseek`'s total monthly cost) — the classic Layer-2-swamps-
Layer-1 inversion. `deepseek-v4-flash` is a different and more striking
story: it is not even the cheapest model by token price (`llama` is), but
its combination of a low L1 *and* the best measured accuracy of any model
tested makes it the cheapest overall by a wide margin — 6x cheaper than
`gemini`, the previous leader, and 55.8x cheaper than `llama`. Layer 1
never exceeds $0.006/run for any model tested; Layer 2 ranges from $0.084
to $4.813 — the entire monthly cost ranking is decided by Layer 2, not
Layer 1, exactly as the earlier measurement showed, just with a different
model on top.

## The cost ledger — four levers, measured before/after

| Lever | What it attacks | Before | After | Change |
|---|---|---|---|---|
| **1. Tool block size** | `B`, re-sent every turn | 7 tools, stub descriptors: **1,996 tokens** | 6 tools, full descriptors (current): **2,165 tokens** | **+169 tokens/turn, net** — see the split below |
| **2. Turn count** | The quadratic term | Sequential: **828,709** input tokens over 50 cases | Parallel: **648,376** input tokens over 50 cases | **-180,333 tokens (-21.8%)** |
| **3. Observation/descriptor size** | Compounds every later turn | Actual return: **median 113 chars (~29 tokens), max 145 (~37)** | **Identical** in v2; descriptor alone changed | **0 observation-token change**; with the corrected v1 control, v2's system prompt is only 57 tokens larger overall and trial pass rate improves **66.7% vs 64.4%** (+2.3pp) — see below |
| **4. Success rate** | Sets layer 2, the largest layer by far | Weakest trial rate (llama, 36.67%): **$4.814/task, $38,519/mo** | Strongest (deepseek, 98.89%): **$0.086/task, $690/mo** | **-$37,829/month (-98.2%)** — by far the largest lever |

### Lever 1, split into its two real causes

The net "+169 tokens/turn" hides two opposite effects, both measured
exactly (`d6_cost_model.py`'s reconstruction):

```
7 tools, stub descriptors (before any D2 work): 1,996 tokens
6 tools, stub descriptors (D2a's cut, isolated): 1,900 tokens   (-96 tokens)
6 tools, full descriptors  (D2b's fill-in, isolated, current):  2,165 tokens  (+265 tokens)
```

Cutting `get_claim` saved 96 tokens/turn, forever, on every run. Writing
the six `what` one-liners the brief's D2(b) requires cost 265 tokens/turn,
more than twice what the cut saved. Net effect: our prompt is bigger than
the bare reference implementation, not smaller, despite having one fewer
tool. This is not a mistake — the two poka-yoke moves that cost zero
prompt tokens (`get_preauthorisation`'s required `date_of_service`,
`check_decision_gate`'s required-field enforcement) prove the real point:
*an interface constraint is paid once and holds; a prompt instruction is
paid on every call of every run forever.*

### Lever 3, measured against the final 50-case set

`d2b_descriptor_rewrite.md` has the full account. `descriptors_v1.py`
ships the deliberately-worse descriptor the brief and its own docstring
specify: `fails_when` and `irreversible` both blank, and a `returns`
field that is vague *and* costly rather than merely short. v2 wins:
**66.7% (60/90) vs 64.4% (58/90)**, +2.3pp. Folding both layers together:
v1's total expected cost/task is **$2.7053**, v2's is **$2.5365** — v2 is
the cheaper option overall by $0.169/task, because its higher Layer-1 cost
(+$0.0010/run) is swamped by its lower Layer-2 fallback cost from the real
accuracy gain. This is the D2(b) result the brief's own worked argument
describes: a genuine, if modest, win for the six-field rewrite, not a wash
and not a loss.

The actual observation-return control is also measured, not assumed:
`measure_d2b.py` calls `check_coverage` for all 50 valid fixture combinations.
Both arms return the same median 113 characters (~29 tokens), mean 115.32
(~29.32), and maximum 145 (~37), because the tool implementation was held
fixed. This cleanly separates Lever 3's two components: **observation D did
not move; descriptor B increased**, and the live accuracy result measures
whether that larger descriptor earned its repeated cost.

**Which of Levers 1 and 3 dominated, and how we know.** Neither, in our
own measurements — and the reason is itself the finding. Both `get_claim`'s
cut (Lever 1) and `check_coverage`'s descriptor rewrite (the B-half of
Lever 3) are prompt-*prefix* text: paid once per turn, every turn, so
their cost is **linear in T**. The actual *compounding* mechanism Lever 3
names — an observation re-sent on every later turn, so an early one is
paid T-minus-its-turn times — never got exercised in our data, because
D2(b) deliberately held the real observation D fixed at a **constant**
median 113 characters as the experimental control (the paragraph above).
So in this repository's own measurements, compounding cost is not a
Lever-1-vs-3 story at all: it is entirely **Lever 2's story**. D2(c)'s
21.8% token cut is the only place our data shows the quadratic term
actually being attacked — turn count T is the one variable in
`B×T + D×T(T-1)/2` we ever moved while holding the other two fixed. Levers
1 and 3's descriptor-text component, by contrast, only ever moved the
linear `B×T` term, which is why their dollar impact (fractions of a cent)
is dwarfed by Lever 2's real token cut and, far more, by Lever 4's success-
rate swing (the actual measured ranking below).

### Lever 4 — now five real data points, not a sensitivity guess

`d5b_live_battery.md` has the full five-model comparison. The spread here
is the whole story of this section: p ranges from 36.67% to 98.89% across
models that differ in token price by less than 6x, but in total cost/task
by nearly **56x**.

## Sensitivity analysis

±10 percentage points around `gpt-4o-mini`'s measured p=66.67% (the model
used as the baseline throughout D0–D2, so this sensitivity band is the one
most directly comparable to earlier sections):

| | p | Layer 2 | Cost/success | Monthly (8,000/mo) |
|---|---|---|---|---|
| downside | 56.67% (p−10) | $3.2933 | $3.2965 | $26,377 |
| **measured** | **66.67%** | **$2.5333** | **$2.5365** | **$20,297** |
| upside | 76.67% (p+10) | $1.7733 | $1.7765 | $14,217 |

A ±10pp swing in success rate moves the monthly bill by **±$6,080
(±30%)** around the measured point — the dollar swing is identical to the
earlier 40-case measurement (a fixed ±10pp band against the same $7.60
failure cost always moves the bill by the same $6,080, regardless of the
starting `p`); only the percentage share shifted, because the baseline
itself moved from $19,030 to $20,297 when `p` dropped from 68.75% to
66.67% on re-measurement.

## Break-even success rate

The brief's question, now answerable with real numbers instead of an
illustrative table: **how accurate would each cheaper model need to
become to match the cheapest-overall model's total cost/task**?
`d6_cost_model.py` picks that benchmark dynamically (whichever model has
the lowest L1+L2 total) rather than hand-naming one — on the current
50-case measurement it is **`deepseek-v4-flash`, at $0.0857/task**,
not `gemini` as the earlier (40-case) measurement had it. That
dynamic-selection choice is itself the finding: a hardcoded "compare
everything to gemini" benchmark would have gone silently stale the moment
`deepseek` overtook it.

```
break-even p = 1 - (E − C) / failure_cost
```
where `E` = `deepseek`'s total cost/task, `C` = the cheaper model's own
(unchanged) Layer-1 cost/run:

| Model | Currently at | Needs to reach | Gap |
|---|---|---|---|
| gemini-2.5-flash | 93.33% | 98.9% | +5.6pp |
| gpt-4o-mini | 66.67% | 98.9% | +32.2pp |
| qwen-2.5-7b-instruct | 54.44% | 98.9% | +44.5pp |
| llama-3.1-8b-instruct | 36.67% | 98.9% | +62.2pp |

**Reading this**: every model's break-even target lands at essentially the
same place — **~98.9%, `deepseek`'s own measured accuracy** — regardless
of how much cheaper its tokens are. `llama` is only ~1.4x more expensive
than `deepseek` by token price (L1 $0.00088 vs $0.00122) and would still
need to nearly triple its accuracy (36.67% -> 98.9%) to match it
economically. This is the brief's own point, now sharper than the earlier
measurement showed it: **because the failure cost ($7.60) is 1,000x-plus
the per-run token cost of every model tested, token price cannot buy its
way to a lower total cost — only accuracy can**, and the model that turned
out to have both the (near-)lowest token price and the highest accuracy
is not the one this repository's own earlier, smaller-set measurement
would have predicted.

## Conclusion — which cost lever actually matters most

**Lever 4 (success rate) dominates, by roughly two to three orders of
magnitude over every other lever measured in this repository.** Lever 1
(tool block size) moves the bill by ±169 tokens/turn — worth a fraction of
a cent per run. Lever 2 (turn count, parallel calling) saves 21.8% of
input tokens — real, worth keeping, but Layer 1 was never more than
$0.006/run to begin with, so 21.8% of that is still a fraction of a cent.
Lever 3 (descriptor quality), corrected and re-measured against the final
50-case set, is a genuine small win: +2.3pp trial pass rate (66.7% vs
64.4%) for a system prompt only 57 tokens larger overall — real, worth
keeping, but still dollar-fractional next to Lever 4. Lever 4 alone moves
the monthly bill from **$690 to $38,519** across the five models as
currently measured — a **~56x** spread, dwarfing every other lever
combined by roughly two orders of magnitude on its own. For a
claims-first-response system where a wrong answer costs a human 12
minutes, the business lesson from this repository's own measurements is
unambiguous: **pick the most accurate model you can afford, and treat
token price as a rounding error next to it** — exactly the shape of
Problem A's own given numbers (a $38/hour failure cost against sub-cent
token costs). The twist this repository's own re-measurement adds: the
most accurate model was not the most expensive one by token price either
— `deepseek-v4-flash` beat `gemini-2.5-flash` on both accuracy and cost
simultaneously, which is not guaranteed by the argument above and would
not have been visible without running the live battery for real.

## Verification

```
$ python3 d6_cost_model.py
```
Reproduces every number in this document directly from
`results/d5b_live_*.json`, `results/d2b_live_*.json`, and
`measure_parallel.py` — no hand-typed figures.
