# D6 — the cost-to-serve model

Uses the Class 5 three-layer model, computed in `d6_cost_model.py` directly
from this repository's committed result files (`results/d5b_live_*.json`,
`results/d2b_live_*.json`, `measure_parallel.py`) — every number below is
measured, not estimated, now that all five D5(b) models plus the D2(b)
v1/v2 pair have real live data.

## Problem A's given inputs (Appendix A)

- Volume: **8,000 claims/month**
- Failure cost: claims assessor at **$38/hour**, **12 minutes** per
  escalated claim = **$7.60**

## Layer 1 — AI variable cost

`input_tokens × input_price + output_tokens × output_price`, measured per
model from its own live battery (80 trials each, real OpenRouter usage):

| Model | Input tok/run | Output tok/run | L1 (variable)/run |
|---|---|---|---|
| gemini-2.5-flash | 15,000 | 563 | $0.00591 |
| deepseek-v4-flash | 12,887 | 1,006 | $0.00120 |
| gpt-4o-mini | 18,574 | 534 | $0.00311 |
| qwen-2.5-7b-instruct | 19,197 | 670 | $0.00205 |
| llama-3.1-8b-instruct | 19,369 | 940 | $0.00104 |

## Layer 2 — expected fallback cost

`(1 - success_rate) × $7.60`, using each model's real D5(b) case-level
pass rate:

| Model | p (measured) | L2 (fallback)/task |
|---|---|---|
| gemini-2.5-flash | 97.5% | $0.1900 |
| deepseek-v4-flash | 90.0% | $0.7600 |
| gpt-4o-mini | 70.0% | $2.2800 |
| qwen-2.5-7b-instruct | 50.0% | $3.8000 |
| llama-3.1-8b-instruct | 35.0% | $4.9400 |

## Layer 3 — fixed monthly cost, stated assumption

No server: fixture files and the scripted harness cost nothing to run. The
one recurring cost assumed here is a monthly live re-run of the evaluation
battery for regression monitoring (40 cases, cheapest measured model) —
**$5.00/month**. This is a stated assumption, not a measurement; the brief
does not fix a figure for this layer.

## D6 outputs — all five models, ranked by total cost/task

| Model | Cost/task (L1) | Fallback cost/task (L2) | Total expected cost/task | Monthly @ 8,000 |
|---|---|---|---|---|
| **gemini-2.5-flash** | $0.0059 | $0.1900 | **$0.1959** | **$1,572** |
| deepseek-v4-flash | $0.0012 | $0.7600 | $0.7612 | $6,095 |
| gpt-4o-mini | $0.0031 | $2.2800 | $2.2831 | $18,270 |
| qwen-2.5-7b-instruct | $0.0021 | $3.8000 | $3.8021 | $30,421 |
| llama-3.1-8b-instruct | $0.0010 | $4.9400 | $4.9410 | $39,533 |

**This ranking inverts raw token price entirely.** `llama-3.1-8b-instruct`
is the *cheapest* model by token cost (L1 = $0.00104/run, ~5.7x cheaper
than `gemini`) and the *most expensive* model overall (~25x `gemini`'s
total monthly cost), because Layer 2 swamps Layer 1 by two to three orders
of magnitude for every model except `gemini`. Layer 1 never exceeds
$0.006/run for any model tested; Layer 2 ranges from $0.19 to $4.94 —
the entire monthly cost ranking is decided by Layer 2, not Layer 1.

## The cost ledger — four levers, measured before/after

| Lever | What it attacks | Before | After | Change |
|---|---|---|---|---|
| **1. Tool block size** | `B`, re-sent every turn | 7 tools, stub descriptors: **1,996 tokens** | 6 tools, full descriptors (current): **2,165 tokens** | **+169 tokens/turn, net** — see the split below |
| **2. Turn count** | The quadratic term | Sequential: **649,111** input tokens over 40 cases | Parallel: **513,037** input tokens over 40 cases | **-136,074 tokens (-21.0%)** |
| **3. Observation/descriptor size** | Compounds every later turn | v1 `check_coverage` descriptor, live on gpt-4o-mini: **62.5% pass, $0.2362/80 trials** | v2 (current), live: **70.0% pass, $0.2485/80 trials** | **+7.5pp pass rate for +$0.0123 total** — see below |
| **4. Success rate** | Sets layer 2, the largest layer by far | Weakest measured model (llama, 35%): **$4.94/task, $39,533/mo** | Strongest measured model (gemini, 97.5%): **$0.196/task, $1,572/mo** | **-$37,961/month (-96.0%)** — by far the largest lever |

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

### Lever 3, now measured live, not just statically

`d2b_descriptor_rewrite.md` has the full case-by-case account. Headline:
the vague v1 descriptor costs 118 tokens/turn *less* than v2, but that
saving is economically invisible ($0.00016/run) next to what it costs in
accuracy — a 7.5-point drop in case-level pass rate, concentrated in the
negative cases (40% vs 50%). Folding both layers together: v1's total
expected cost/task is *higher* than v2's despite its smaller prompt,
because Layer 2's accuracy loss outweighs Layer 1's token saving by two
orders of magnitude, the same pattern Lever 4 shows at a larger scale.

### Lever 4 — now five real data points, not a sensitivity guess

`d5b_live_battery.md` has the full five-model comparison. The spread here
is the whole story of this section: p ranges from 35% to 97.5% across
models that differ in token price by less than 6x, but in total cost/task
by **25x**.

## Sensitivity analysis

±10 percentage points around `gpt-4o-mini`'s measured p=70.0% (the model
used as the baseline throughout D0–D2, so this sensitivity band is the one
most directly comparable to earlier sections):

| | p | Layer 2 | Cost/success | Monthly (8,000/mo) |
|---|---|---|---|---|
| downside | 60.0% (p−10) | $3.0400 | $3.0431 | $24,350 |
| **measured** | **70.0%** | **$2.2800** | **$2.2831** | **$18,270** |
| upside | 80.0% (p+10) | $1.5200 | $1.5231 | $12,190 |

A ±10pp swing in success rate moves the monthly bill by **±$6,080
(±33%)** around the measured point — this is the same shape the earlier,
single-model version of this table showed, now anchored to a genuinely
measured p rather than one live battery's single draw plus a stated
uncertainty band.

## Break-even success rate

The brief's question, now answerable with real numbers instead of an
illustrative table: **how accurate would each cheaper model need to
become to match `gemini-2.5-flash`'s total cost/task** (currently the
cheapest overall, at $0.1959/task)?

```
break-even p = 1 - (E − C) / failure_cost
```
where `E` = gemini's total cost/task, `C` = the cheaper model's own
(unchanged) Layer-1 cost/run:

| Model | Currently at | Needs to reach | Gap |
|---|---|---|---|
| deepseek-v4-flash | 90.0% | 97.4% | +7.4pp |
| gpt-4o-mini | 70.0% | 97.5% | +27.5pp |
| qwen-2.5-7b-instruct | 50.0% | 97.4% | +47.4pp |
| llama-3.1-8b-instruct | 35.0% | 97.4% | +62.4pp |

**Reading this**: every model's break-even target lands at essentially the
same place — **~97.4%, gemini's own measured accuracy** — regardless of
how much cheaper its tokens are. `llama` is 5.7x cheaper than `gemini` by
token price and would still need to *more than double* its accuracy (35%
→ 97.4%) to match it economically. This is the brief's own point, now with
five real models instead of an illustrative pair: **because the failure
cost ($7.60) is 1,000x-plus the per-run token cost of every model tested,
token price cannot buy its way to a lower total cost — only accuracy can.**

## Conclusion — which cost lever actually matters most

**Lever 4 (success rate) dominates, by roughly two orders of magnitude
over every other lever measured in this repository.** Lever 1 (tool block
size) moves the bill by ±169 tokens/turn — worth a fraction of a cent per
run. Lever 2 (turn count, parallel calling) saves 21% of input tokens —
real, worth keeping, but Layer 1 was never more than $0.006/run to begin
with, so 21% of that is still a fraction of a cent. Lever 3 (descriptor
quality) moves accuracy by 7.5 points for a token cost so small it's
foldable into Lever 1. Lever 4 alone moves the monthly bill from
**$1,572 to $39,533** across the five models actually measured — a
**25x** spread, dwarfing every other lever combined. For a claims-first-
response system where a wrong answer costs a human 12 minutes, the
business lesson from this repository's own measurements is unambiguous:
**pick the most accurate model you can afford, and treat token price as a
rounding error next to it** — exactly the shape of Problem A's own given
numbers (a $38/hour failure cost against sub-cent token costs), now
confirmed with five real models instead of assumed.

## Verification

```
$ python3 d6_cost_model.py
```
Reproduces every number in this document directly from
`results/d5b_live_*.json`, `results/d2b_live_*.json`, and
`measure_parallel.py` — no hand-typed figures.
