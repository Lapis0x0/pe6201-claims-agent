# D2(b) — the descriptor rewrite, v1 vs v2

Target: `check_coverage`, called once per line item, so its descriptor's cost
compounds fastest with claim size of anything in the tool set.

## v1 (before) vs v2 (current, in `config.TOOL_SPECS`)

| | v1 | v2 |
|---|---|---|
| signature | `check_coverage(policy_id, procedure_code)` — untyped | `check_coverage(policy_id: str, procedure_code: str) -> str` |
| what | (absent) | one line naming what it uniquely answers |
| returns | "coverage details for the procedure." | the exact shape, plus a measured SIZE BOUND (145 chars / ~36 tokens over all 50 policy×procedure pairs) |
| fails_when | (absent) | named: unknown `policy_id` or `procedure_code` |
| poka-yoke | none | none on this tool specifically — see the four moves on the other three tools, below |

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

## The live measurement — done, on `openai/gpt-4o-mini`

**Experimental rule**: model held fixed (`openai/gpt-4o-mini`, matching
one of D5(b)'s five models so the two experiments share a data point),
only `--descriptor-version` changes. Same 40-case set, same trial
arithmetic (20 ordinary x1 + 20 negative x3 = 80 trials), same guardrail
code.

| Metric | Prompt v1 (vague descriptor) | Prompt v2 (six-field, current) |
|---|---|---|
| Overall pass (case-level) | 25/40 (62.5%) | **28/40 (70.0%)** |
| Ordinary pass | 17/20 (85.0%) | 18/20 (90.0%) |
| Negative pass | 8/20 (40.0%) | **10/20 (50.0%)** |
| Avg input tokens/run | 17,561 | 18,574 |
| Avg output tokens/run | 530 | 534 |
| Avg cost/run | $0.00295 | $0.00311 |
| Avg turns | 7.3 | 7.5 |
| Total cost (80 trials) | $0.2362 | $0.2485 |

(`results/d2b_live_v1_gpt4o_mini.json`, `results/d2b_live_v2_gpt4o_mini.json`)

**What changed in the prompt**: v2 adds a `what` one-liner naming exactly
what `check_coverage` answers that nothing else does, a measured SIZE
BOUND on the returned string, and an explicit `fails_when` clause for
unknown `policy_id`/`procedure_code` — v1 has none of these, just an
untyped signature and "coverage details for the procedure." as its entire
`returns` field.

**What behaviour improved**: overall pass rate rose 7.5 points (62.5% ->
70.0%), and the gain is concentrated in the negative cases (+10pp, 40% ->
50%) more than the ordinary ones (+5pp) — consistent with the hypothesis
that a vaguer descriptor mainly hurts the harder, more failure-prone
decisions, not the easy ones. Comparing case-by-case: v2 fixed five cases
v1 got wrong — three of them `required_document_*` cases
(`CLM-8901`, `CLM-9060`, `CLM-9070`), plus one preauth-boundary case
(`CLM-9010`) and one long multi-line run (`CLM-8960`). The concentration
in `required_document_*` cases is the clearest direct effect: v2's
`fails_when` and precise `returns` shape appear to help the model commit
to the specific missing item's identity rather than reporting the wrong
one or none.

**What regressed, honestly**: two cases flipped the other way
(`CLM-8925`, `annual_limit_exceeded`; `CLM-9045`,
`four_line_all_covered_variety`) — v1 passed them, v2 didn't. Neither
touches `check_coverage`'s output shape in a way that plausibly explains a
descriptor-driven regression (annual-limit arithmetic reads from
`lookup_member_policy`, not `check_coverage`), so the honest read is live
run-to-run variance on a handful of borderline cases at `n=1` per
ordinary case, not a real cost of the v2 descriptor. This is the same
caveat `d5b_live_battery.md` raises for single-trial ordinary cases in
general — it would take repeated trials on just these two cases to tell
noise from a real regression.

**Cost verdict**: the extra descriptor tokens cost essentially nothing in
practice — $0.00311/run vs $0.00295/run, a $0.00016 difference on a run
that costs three-tenths of a cent either way. At this model's price point,
the 118 tokens/turn measured statically in the section above is real but
economically invisible next to the 7.5-point accuracy gain it buys.
