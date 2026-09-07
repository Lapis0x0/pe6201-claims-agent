# D4 — the evaluation set: design notes

40 cases (15 shipped + 25 added), all outcome-graded against
`expected_outcomes_A.json`, all isolated (no case depends on another having
run — `harness.py` truncates `decisions.jsonl` at the start of every run).

## Distribution

| Outcome | Shipped | Added | Total |
|---|---|---|---|
| `approve_in_principle` | 6 | 14 | 20 |
| `request_document` (negative) | 3 | 5 | 8 |
| `escalate` (negative) | 6 | 6 | 12 |
| **Total** | **15** | **25** | **40** |
| **Negative** | **9** | **11** | **20** |

20/40 negative is well above the brief's 8-negative floor for a 40-case set.
This is a deliberate choice, not an accident of how the families happened to
fall: this problem's routing rule has real edge-case density (boundary dates,
near-limit claims, three distinct pre-authorisation failure shapes, two
distinct document-absence instances, two distinct duplicate pairs, four
distinct hostile-narrative shapes), and each of those is a genuinely
different thing for the agent to get right or wrong. A production claim
stream would not actually be 50% negative — that realism belongs in D6's
volume assumption (8,000 claims/month from Appendix A), not in an evaluation
set whose job is to separate a careful agent from a plausible-looking one.

## The 25 added cases, by what they test

All 25 are built from `EXTRA_CLAIMS` alone in `make_fixtures_A.py` — no new
members, policies, hospitals, procedures, pre-authorisations or
required-document rules were needed; every new case reuses the shipped
supporting data, which kept the referential-integrity surface small.

**Approve (14)** — mostly business-as-usual variety (two-line, four-line,
five-line claims; a second exclusion instance on a different policy; a
non-panel hospital with no other complication) plus four *boundary* tests
that don't appear in the shipped 15: a pre-authorisation's own `valid_from`
and `valid_to` dates (inclusive), a policy's own `start_date` (inclusive),
and a date close to but before a policy's `end_date`. These boundary cases
exist because `get_preauthorisation`'s date comparison in `tools.py` is
`valid_from <= date_of_service <= valid_to` — inclusive on both ends — and
nothing in the shipped set exercised either edge. The policy start/end
boundary isn't enforced in code (the model reads the dates off
`lookup_member_policy`'s prose and reasons about them), so these scripted
labels fix the same inclusive convention for consistency across the system,
and say so in their `note` field.

**Request-document (5)** — two more pre-authorisation-absent cases (a
different member each, one of them the same procedure as the shipped
expired-record case, to separate "no record" from "expired record" as
distinct failure shapes), a preauth-expiry *boundary* case (one day past
`valid_to` — the request-document mirror of the approve-side boundary test),
and a second required-document-absent case on the discharge-summary rule
rather than the shipped itemised-bill instance.

**Escalate (6)** — the mirror of the shipped `outside_policy_dates` case
(after `end_date` rather than before `start_date`), a second `policy_lapsed`
instance, an `annual_limit_exceeded` case that exceeds by exactly 1 (see
below), a second true duplicate against a different `decided_claims` row
than the shipped one, and two new hostile-narrative shapes: a fake
claims-manager pre-approval, and an instruction to skip the
pre-authorisation check specifically. Both new injection cases are built so
the *underlying* claim is otherwise resolvable (a valid pre-authorisation is
on file, or the real check would have caught the gap anyway) — proving the
escalation is caused by the hostile text, not by the model stumbling into a
genuine business gap and mislabelling the reason.

**The boundary pair worth reading together**: `CLM-9085` (claim total 601
against 600 remaining — escalates) only proves a `>` check exists. Read
alone it would also pass under a `>=` check. `CLM-8971` (already shipped:
claim total 170 against 600 remaining — approves) is what rules `>=` out,
since a `>=`-based implementation would wrongly escalate it. The two
together, not either alone, are the evidence that the limit check uses the
correct operator.

## Code check vs judgement check

`harness.check()` asserts, per the FAQ's own definition of a code check —
"the decision field equals the expected value, the single trigger matches,
a required tool appears in the trace, the gated action fired exactly once":

- `decision` — always.
- `letter_issued` — always (the gated action fired exactly once; every one
  of the 40 real business cases ends in a recorded decision).
- `trigger` — for the 12 `escalate` cases.
- `expected_line` — for the 8 `request_document` cases: the procedure code
  the missing item belongs to, a bare identifier (`"62480"`,
  `"discharge_summary"`'s line `"45378"`, etc.), not the free-text
  description of *what's* missing.
- `expected_approved_total` / `expected_refused_total` — for the 20
  `approve_in_principle` cases, cross-checked against each claim's own line
  amounts when the labels were built (`approved_total + refused_total ==
  sum(line amounts)` held for all 20 without needing a single correction).

What stays a **judgement check**, deliberately: the prose in
`missing_document` itself (is "a pre-authorisation reference for procedure
62480, valid on 2026-09-08" actually a usable instruction, or just
"more information required"?), and every case's `must_record` list — read
by `harness.py --judgement-sheet`, scored by a person or a second model,
never by a substring match (Class 4's own demonstration of why a substring
check can pass for the wrong reason is exactly why this stays manual).

## D4's own results and metrics

`python3 harness.py` now prints, beyond the per-trial pass/fail table:

- a **one-row-per-case** results table (case, family, expected, actual,
  trigger, code check, judge — "not graded" until a human or second model
  does that pass, overall pass)
- **case-level pass rate** (40/40), distinct from the trial-level rate,
  which counts negative cases' extra trials
- **pass rate by family** — all 40 families are currently unique (one case
  each), so this doubles as a family checklist
- **ordinary vs. negative pass rate**, separately (20/20 and 20/20)
- **decision confusion** — every `(expected, actual)` mismatch, counted;
  currently empty (`none`)
- **turns**: median, average, min, max (was median/min/max only)

## Run arithmetic for this set

Ordinary cases get 1 trial; negative cases get 3 (they're the ones that flip
between runs, per the brief). With 20 ordinary and 20 negative:

```
runs per model = 20 x 1 + 20 x 3 = 80
```

Above the brief's 56-run "shape we expect" for a 40/8 split, because this
set carries 20 negative cases rather than 8. `harness.py` applies this split
automatically now (`--trials` for ordinary cases, `--negative-trials` for
negative ones, defaulting to 1 and 3): plain `python3 harness.py` already
runs exactly 80 trials, not a uniform 120 — the same shape a live model
would be billed for. All 80 (scripted) are free.

## Verification

```
$ python3 check_my_data.py
Your data hangs together.

$ python3 harness.py
pass rate: 100.0%  (80/80 runs; 20 ordinary cases x 1 trial + 20 negative cases x 3 trials)
case-level pass rate: 40/40 (100.0%)
turns: median 5, average 4.9, min 3, max 6

$ python3 harness.py --sequential
pass rate: 100.0%  (80/80 runs; 20 ordinary cases x 1 trial + 20 negative cases x 3 trials)
case-level pass rate: 40/40 (100.0%)
turns: median 6, average 5.9, min 3, max 10
```
