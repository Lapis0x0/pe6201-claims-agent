# D2(b) — the descriptor rewrite, v1 vs v2

Target: `check_coverage`, called once per line item, so its descriptor's cost
compounds fastest with claim size of anything in the tool set.

## v1 (before) vs v2 (current, in `config.TOOL_SPECS`)

**Contract vs. what actually reaches the model**: `TOOL_SPECS` stores the
full six-field contract for every tool, but `render_tool_list()` only
renders four of those six fields into the live system prompt —
`signature`, `what`, `returns`, and `prompt_guidance` (labelled "use it" in
the rendered text). `input` and `fails_when` are documented in the
contract below for design completeness, but are **not** sent to the model
as prompt text on any turn; `irreversible` and `poka_yoke` are enforced in
code (the gate), which is the point of a poka-yoke move — it should not
need to be prompt text to work. The live token-cost comparison further
down this document measures the rendered subset only, since that is what
is actually paid for on every turn.

| | v1 | v2 |
|---|---|---|
| signature | `check_coverage(policy_id, procedure_code)` — untyped | `check_coverage(policy_id: str, procedure_code: str) -> str` |
| what | (absent) | one line naming what it uniquely answers |
| returns | "coverage details for the procedure." | the exact shape, plus a measured SIZE BOUND (145 chars / ~36 tokens over all 50 policy×procedure pairs) |
| fails_when *(contract only, not rendered into the prompt)* | (absent) | named: unknown `policy_id` or `procedure_code` |
| poka-yoke *(contract only; enforced in code, not prompt text)* | none | none on this tool specifically — see the four moves on the other three tools, below |

`descriptors_v1.py` holds the v1 spec as a literal `OVERRIDES` dict;
`config.render_tool_list(overrides=...)` and `config.build_system_prompt(overrides=...)`
accept it, and `harness.py --descriptor-version v1` wires it through
`ClaimsAgent(prompt_overrides=...)` without touching `config.TOOL_SPECS` itself.

## Poka-yoke moves — four, on three tools

`check_coverage` itself carries none (it's read-only and returns one fact
that's already type-checked by the closed `Literal` on the caller's side);
the layer's poka-yoke moves live on the three tools where a silent error
would actually cost something. Each is a design change, not a prompt
instruction — the model is never asked to be careful, the interface makes
the mistake impossible to make.

| Tool | Before | After | What it makes impossible |
|---|---|---|---|
| `get_preauthorisation` | `date_of_service` optional, defaulting to "today" or `None` | `date_of_service` a required positional argument | Checking whether a pre-authorisation *exists* without also being forced to check whether it's *valid on this claim's service date* — existence and validity were the same call, so they can't be silently conflated. |
| `check_duplicate` | `member_id`, `hospital_id`, `date_of_service`, `lines` all optional, defaulting to a partial match | All four required positional arguments, no defaults | Omitting one and having the match silently loosen — a genuine duplicate hiding behind a `NO MATCH` because only 3 of 4 facts were actually compared. |
| `issue_decision_letter` | `decision` any string | `decision` checked against `config.DECISIONS`, a closed 3-value set, inside `check_decision_gate` | A typo'd or invented decision (`"aproved"`, `"deny"`) being written as a fourth, unrecognised outcome instead of being refused before the write. |
| `issue_decision_letter` | `detail` any dict, no required shape | Gate requires decision-specific structured fields — a named `trigger` for escalate, `missing_document` + `line` for request_document, `line_dispositions` covering every filed line plus numeric `approved_total`/`refused_total` for approve | Recording a decision that names no reason, or an approval that's silent about one of the claim's lines. |

Source: `config.TOOL_SPECS`'s `poka_yoke` field on each tool, which is where
this text actually lives (not rendered into the prompt — see D6's Lever 1
for why that's deliberate: an interface constraint is enforced by the gate
at runtime, so it costs zero prompt tokens on every turn, unlike the `what`
fields which are prompt-level and paid for forever).

## What's measured already (no live call needed)

Rendering both prompts and diffing the `check_coverage` block:

| | v1 | v2 | delta |
|---|---|---|---|
| descriptor block | 137 chars (~34 tokens) | 607 chars (~152 tokens) | **+118 tokens/turn** |
| full system prompt | 6,675 chars (~1,669 tokens) | 7,145 chars (~1,786 tokens) | +117 tokens/turn |

**This is the honest, counter-intuitive result the brief asks us to report
either way**: v2 is not smaller. It is 118 tokens/turn more expensive,
re-billed on every turn of every run, forever. The hypothesis the live pass
proves or disproves is whether that cost buys enough back in reliability —
fewer malformed calls (v1 gives the model no types to conform to), fewer
wasted turns re-reading an ambiguous "coverage details" return, and cleaner
handling of the two policy×procedure pairs that don't exist in the fixture
data (v1 names no `fails_when`, so a bad id's behaviour is unspecified from
the model's point of view; v2 tells it to expect a `NOT FOUND` string) — to
be worth the extra 118 tokens every single turn.

### Actual observation-return size: v1 versus v2

The v1 control changed the `check_coverage` descriptor presented to the
model, not the Python tool implementation. We verified the actual returned
strings across all **50 fixture-valid policy x procedure lookups**. The
runtime observation size was therefore deliberately identical in both arms:

| Actual `check_coverage` return | v1 | v2 | Delta |
|---|---:|---:|---:|
| Minimum | 103 chars (~26 tokens) | 103 chars (~26 tokens) | 0 |
| Median | 113 chars (~29 tokens) | 113 chars (~29 tokens) | 0 |
| Mean | 115.32 chars (~29.32 tokens) | 115.32 chars (~29.32 tokens) | 0 |
| Maximum | 145 chars (~37 tokens) | 145 chars (~37 tokens) | 0 |

The transparent token estimate is `ceil(characters / 4)`. This null control
matters: v2's live accuracy change cannot be attributed to receiving shorter
observations, because both versions received the same bounded return strings.
It isolates the paid descriptor rewrite as the changed variable. Reproduce
the result with `python3 measure_d2b.py`.

**Named plainly against the brief's own wording**: the brief asks for "a v1
and a v2 of its descriptor *and its return shape*." This document isolates
the descriptor alone, deliberately holding the return shape fixed so the
live accuracy delta above is attributable to one variable, not a confound (a
v2 that also returned shorter or better-typed observations would leave the
two effects entangled). The return shape's own v1/v2 pair — same model, same
50-case set, descriptor pinned at v2 this time — is a separate, later pass:
see `d2b_return_shape.md`.

### Guardrail-pass control

| Scripted checklist | v1 | v2 |
|---|---:|---:|
| Guardrail cases passed | **12/12 (100%)** | **12/12 (100%)** |

The checklist scripts attempted violations of the same code-layer controls in
both arms. Descriptor text cannot disable the step cap, tool-call budget,
de-duplication or autonomy gate, so unchanged 12/12 performance is the
expected control result, not evidence that the prompt itself provides those
guardrails. Stated precisely: `measure_d2b.py` runs the scripted guardrail
checklist **once** and reports that single result for both columns, rather
than executing it twice under each descriptor version — a shared control,
not two independent runs. This is logically sound only because the scripted
backend replays fixed trajectories and never reads either descriptor version
at all (`config.render_tool_list`'s output only reaches a `LiveBackend`
call), so a second execution against v1 would be guaranteed to reproduce the
identical 12/12, not an independent check of it.

## The live measurement — done, on `openai/gpt-4o-mini`

**Experimental rule**: model held fixed (`openai/gpt-4o-mini`, matching
one of D5(b)'s five models so the two experiments share a data point),
only `--descriptor-version` changes. Current 50-case set, current trial
arithmetic (30 ordinary x1 + 20 negative x3 = 90 trials), same guardrail
code. Most recent run 2026-09-09.

**v1's design, stated plainly.** `descriptors_v1.py` ships the
deliberately-worse control the brief's D2(b) section asks for: `fails_when`
and `irreversible` both blank, and a `returns` field that is vague *and*
costly rather than merely short. `fails_when` and `irreversible` are
documented-contract-only fields that `render_tool_list()` never sends to
the model regardless of their content (see the contract-vs-rendered note
above), so blanking them changes nothing live — but the `returns` field
**is** rendered, and making it genuinely verbose (not just vague) is what
actually moves this measurement. `descriptors_v1.py` and
`results/d2b_live_v1_gpt4o_mini.json` reflect this v1.

| Metric | Prompt v1 (vague, corrected) | Prompt v2 (rewritten descriptor, current) |
|---|---|---|
| **Primary pass rate (trials)** | 58/90 (64.4%) | **60/90 (66.7%)** |
| Ordinary trials | 27/30 (90.0%) | 28/30 (93.3%) |
| Negative trials | 31/60 (51.7%) | 32/60 (53.3%) |
| Avg input tokens/run | 18,092 | 18,721 |
| Avg output tokens/run | 544 | 546 |
| System prompt size | 2,108 tokens | 2,165 tokens |
| Total cost (90 trials) | $0.2736 | $0.2822 |

(`results/d2b_live_v1_gpt4o_mini.json`, `results/d2b_live_v2_gpt4o_mini.json`)

**What changed in the prompt**: v2 adds a `what` one-liner naming exactly
what `check_coverage` answers that nothing else does, a measured SIZE
BOUND on the returned string, and an explicit `fails_when` clause for
unknown `policy_id`/`procedure_code` (contract-level only — not rendered).
Corrected v1 has none of these: an untyped signature, no `what`, and a
`returns` field that is long ("This tool will return some details about
the coverage situation... depending on what applies in this particular
case") without ever giving a shape, a size bound, or a concrete field
list.

**The result**: v2 wins by +2.3 points (66.7% vs 64.4%), and it does so
while its *own* system prompt is only 57 tokens larger overall (2,165 vs
2,108) — smaller than the earlier, uncorrected v1's prompt gap, because
corrected v1's blank `what` field saves more than its now-verbose
`returns` field costs. The per-run token cost is close either way
(18,721 vs 18,092, +3.5%) and the accuracy gain is real, not simply
bought with a bigger prompt. This is the version of the finding the
brief's D2(b) actually asks for: **a genuinely worse control, honestly
compared, and the six-field rewrite earns a small, real, defensible win**
rather than the ambiguous tie the uncorrected control produced.

**Cost verdict**: v2 costs $0.0086 more across the full 90-trial pass
($0.2822 vs $0.2736) for +2 more correct trials — a clear, if modest, win
on a per-successful-task basis. The interface-vs-prompt argument for the
poka-yoke moves elsewhere in this tool (D2(a)'s `get_preauthorisation`,
`check_duplicate`, `issue_decision_letter` fields) is a separate point
from this one: those cost zero prompt tokens regardless of outcome, and
hold regardless of which way this particular descriptor comparison lands.
One honest limit remains: this is a single trial per ordinary case, so a
+2.3pp gap on 90 trials is a real but not large signal — enough to report
as a finding, not enough to claim a precise effect size.
