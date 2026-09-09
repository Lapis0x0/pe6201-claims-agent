# D2(b) — the return-shape rewrite, v1 vs v2

The brief's D2(b) asks for a v1/v2 of the tool's descriptor *and* its return
shape. `d2b_descriptor_rewrite.md` covers the descriptor half, deliberately
holding the return shape fixed. This is the other half: the descriptor is
now pinned at v2 (current, best) in **both** arms, and the runtime value
`check_coverage` actually hands back is the only thing that changes.

## v1 (prose, unchanged from before) vs v2 (typed JSON)

```
v1: procedure 47120 (Laparoscopic appendicectomy): covered by POL-3310.
    requires_preauth: no. required_document: none
v2: {"policy_id": "POL-3310", "procedure_code": "47120",
     "description": "Laparoscopic appendicectomy", "covered": true,
     "exclusion_rule": null, "requires_preauth": false,
     "required_document": null}
```

Same facts, two shapes: v1 identifies each field by English wording, v2 by
an explicit key. `tools.py`'s `ClaimsTools(return_shape_version=...)`
selects the shape at construction time; `harness.py --return-shape-version
{v1,v2}` wires it through (default `v1`, so the scripted backend and every
existing script are unaffected). Both a `NOT FOUND` and a real lookup have a
v2 form — see `tools.py`'s `check_coverage`.

## What's measured already (no live call needed)

`python3 measure_return_shape.py` renders the descriptor once (proving it is
untouched) and diffs the actual return value over all 50 fixture-valid
policy x procedure lookups:

| Actual `check_coverage` return | v1 (prose) | v2 (typed JSON) | Delta |
|---|---:|---:|---:|
| Minimum | 103 chars (~26 tokens) | 181 chars (~46 tokens) | +20 tokens |
| Median | 113 chars (~29 tokens) | 193 chars (~49 tokens) | +20 tokens |
| Mean | 115.32 chars (~29.32 tokens) | 194.60 chars (~49.08 tokens) | +19.76 tokens |
| Maximum | 145 chars (~37 tokens) | 216 chars (~54 tokens) | +71 chars |

Unlike the descriptor arm's null result, this is not free: JSON's quoting
and keys cost real tokens on every call, paid once per line item, every
turn, forever. Descriptor tokens are identical in both arms (1,055, printed
by the same script) — this isolates the return shape as the only variable.

## Live result

Same model (gpt-4o-mini), same current 50-case/90-trial set, descriptor
pinned at v2, only the return shape moves:

| | v1 (prose) | v2 (typed JSON) | Delta |
|---|---:|---:|---:|
| Trial pass rate | 63/90 (70.0%) | 67/90 (74.4%) | +4.4pp |
| Ordinary cases (30 x1 trial) | 27/30 | 27/30 | 0 |
| Negative cases, strict (all 3 trials pass) | 9/20 | 10/20 | +1 case |

The gain is entirely on the negative side — cases whose correct answer is
`escalate` or `request_document`, not `approve_in_principle`. Ordinary cases
were identical in both arms. This is consistent with the return shape
mattering most exactly where the model has to notice one specific field
(an exclusion, a missing document, a `NOT FOUND`) rather than aggregate
several covered lines into a total: a labelled JSON key is harder to miss
than a clause inside a sentence.

**Cost of the gain**: +4.4pp trial-level accuracy for +19.76 tokens/call
mean, paid on every `check_coverage` call of every run. At Problem A's
volume (D6), that is a small, real, ongoing cost for a small, real,
ongoing accuracy gain — not free, and not obviously worth it either;
recorded here as a measured tradeoff, not a recommendation either way.

Reproduce with:
```
python3 harness.py --live --model openai/gpt-4o-mini --descriptor-version v2 --return-shape-version v1 --json results/d2b_return_shape_v1_gpt4o_mini.json
python3 harness.py --live --model openai/gpt-4o-mini --descriptor-version v2 --return-shape-version v2 --json results/d2b_return_shape_v2_gpt4o_mini.json
```

### Guardrail-pass control

`guardrail_checklist.py` never passes `return_shape_version` (it exercises
gate logic, not `check_coverage`'s observation), so both arms inherit the
default v1 shape and the existing 12/12 result is unaffected either way.
