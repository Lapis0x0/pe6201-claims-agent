# D1 — the agent: sample traces and an instrumented decision record

The agent (`agent.py`'s `ClaimsAgent`) is a single ReAct loop: Thought →
Action → Observation → repeat → Final. It reads a claim, decides which
tool(s) to call next based on what the last observation said, and stops
with one of three outcomes. Nothing about the sequence is fixed in code —
`config.py`'s prompt states the routing rules, but the model decides which
rule applies and when to stop.

## Three traces, one per outcome

**Approve** (`CLM-8850`, `single_line_short_run`) — 5 turns, 5 tool calls,
no guardrail events:
```json
{
  "approved_total": 180, "refused_total": 0,
  "hospital": "H-207 Mount Elizabeth East, on panel",
  "policy": "POL-6001 active 2026-06-01 to 2027-05-31, 15,000 remaining",
  "duplicate_check": "no match. CLM-8702 shares the member, hospital and line item but its date of service is 2026-09-02, not 2026-09-04",
  "line_dispositions": [{"code": "99213", "amount": 180, "disposition": "approved",
                         "basis": "covered by POL-6001; no pre-authorisation and no supporting document required"}],
  "narrative_check": "no instruction found in the member narrative"
}
```

**Ask** (`CLM-8888`, `preauth_absent`) — 6 turns, 8 tool calls. Note the
record resolves every other line even though the claim as a whole is
blocked on one missing item — an ask is not "stop and say nothing":
```json
{
  "missing_document": "a pre-authorisation reference for procedure 62480, valid on 2026-09-08",
  "line": "62480",
  "basis": "check_coverage returned requires_preauth yes for 62480, and get_preauthorisation returned no record on file for member M-6118 and that procedure",
  "also_recorded": [
    {"code": "31255", "amount": 300, "disposition": "refused", "basis": "excluded by POL-7220 under EX-14 cosmetic dermatology"},
    {"code": "47120", "amount": 900, "disposition": "payable", "basis": "covered by POL-7220; held pending the missing authorisation for the claim as a whole"}
  ],
  "narrative_check": "no instruction found in the member narrative"
}
```

**Escalate** (`CLM-8910`, `policy_lapsed`) — 3 turns, 2 tool calls, the
shortest of the three: the policy lookup alone is disqualifying, so the
agent never prices a line:
```json
{
  "trigger": "policy_lapsed", "escalate_to": "human claims assessor",
  "basis": "POL-5588 has status lapsed. The three line items were not priced: a lapsed policy will not pay them",
  "narrative_check": "no instruction found in the member narrative"
}
```

**The evidence this set of three already makes**: turn count is not a
constant and not a function of which outcome the claim reaches — it is a
function of how much the claim requires *checking*. The escalate case
(3 turns) is shorter than both the approve (5) and the ask (6) cases,
because a lapsed policy ends the investigation immediately, while the ask
case needed a pre-authorisation lookup neither of the others triggered.

## Instrumentation captured on every run

`AgentResult` (`agent.py`) records, for every run without exception:

| Field | What it is |
|---|---|
| `steps` | turns |
| `tool_calls` | tool invocations, counting only ones that actually executed (a de-duplication refusal doesn't count twice) |
| `prompt_tokens` / `completion_tokens` | tokens in / out (0 on the scripted backend by design; real, measured usage on `LiveBackend`) |
| `runtime_seconds` | real wall-clock time for the run |
| `guardrails_fired` | every guardrail EVENT during the run — `action_deduplication`, `budget_ceiling`, `step_cap`, `autonomy_gate`, `unparseable_output`, `invalid_arguments` — not just the one that (maybe) ended it. A run that gets one gate refusal and then self-corrects still shows that refusal here even though it goes on to finish normally. |
| `trace` | the full message list — the evidence trail |
| `decision`, `detail` | the final decision |

`harness.py`'s per-row output (`--json`) adds `cost_usd`, computed from
measured tokens against `PRICE_PER_MILLION` for models this project has
actually run (`openai/gpt-4o-mini`, `deepseek/deepseek-chat`) — `None`
("unknown", not a guess) for any other model, and exactly `0.0` on the
scripted backend since no tokens were spent.

## Two records, not one — the harness's and the gated action's own

Earlier drafts of this document showed only `harness.py`'s `AgentResult`
below and called it "the instrumented decision record" — imprecise,
because that record lives in the harness's `--json` export, not in
`decisions.jsonl`, the file the gated action itself writes. The brief's
own worked example is the shape of *that* file, so here both are shown,
and the correction is real: the persisted record was, until this fix,
smaller than the brief's example (`claim_id`/`decision`/`detail` only —
no timestamp, evidence, autonomy, gate status, turn count or cost). It now
carries all of those fields, matching the brief's own worked example
field-for-field except naming (`claim_id` rather than `case_id`, and a
structured `detail` object rather than a single `reason` sentence — see
the note below both records for why those two are kept as they are).

**`AgentResult`** (`agent.py`), the harness-level run summary, for every
run without exception:

| Field | What it is |
|---|---|
| `steps` | turns |
| `tool_calls` | tool invocations, counting only ones that actually executed (a de-duplication refusal doesn't count twice) |
| `prompt_tokens` / `completion_tokens` | tokens in / out (0 on the scripted backend by design; real, measured usage on `LiveBackend`) |
| `runtime_seconds` | real wall-clock time for the run |
| `guardrails_fired` | every guardrail EVENT during the run — `action_deduplication`, `budget_ceiling`, `step_cap`, `autonomy_gate`, `unparseable_output`, `invalid_arguments` — not just the one that (maybe) ended it. A run that gets one gate refusal and then self-corrects still shows that refusal here even though it goes on to finish normally. |
| `trace` | the full message list — the evidence trail |
| `decision`, `detail` | the final decision |

`harness.py`'s per-row output (`--json`) adds `cost_usd`, computed from
measured tokens against `config.PRICE_PER_MILLION` for models this project
has actually run — `None` ("unknown", not a guess) for any other model, and
exactly `0.0` on the scripted backend since no tokens were spent.

```json
{
  "case_id": "CLM-8842",
  "decision": "approve_in_principle",
  "steps": 5,
  "tool_calls": 8,
  "prompt_tokens": 0,
  "completion_tokens": 0,
  "cost_usd": 0.0,
  "runtime_seconds": 0.00031,
  "guardrails_fired": [],
  "letter_issued": true,
  "detail": { "...": "the same detail object shown in the gated record below" }
}
```

**`decisions.jsonl`**, the gated action's own append-only log — the file
`tools.ClaimsTools.issue_decision_letter` actually writes, and what a
marker re-running the harness would find if they inspected the file the
brief's D1 example describes rather than the harness's summary of it:

```json
{"ts": "2026-09-09T07:58:24+00:00", "claim_id": "CLM-8842", "decision": "approve_in_principle",
 "detail": {
   "approved_total": 2180, "refused_total": 300,
   "hospital": "H-114 Riverside General, on panel",
   "policy": "POL-3310 active 2026-04-01 to 2027-03-31, 9,200 remaining",
   "line_dispositions": [
     {"code": "47120", "amount": 1400, "disposition": "approved", "basis": "covered by POL-3310; no pre-authorisation required"},
     {"code": "62480", "amount": 780, "disposition": "approved", "basis": "covered by POL-3310; PA-5521 valid 2026-08-01 to 2026-10-31 authorises the date of service 2026-09-02; discharge_summary supplied"},
     {"code": "31255", "amount": 300, "disposition": "refused", "basis": "excluded by POL-3310 under EX-14 cosmetic dermatology"}
   ],
   "narrative_check": "no instruction found in the member narrative"
 },
 "evidence": ["lookup_member_policy", "check_duplicate", "check_hospital", "check_coverage x3", "get_preauthorisation"],
 "autonomy": "confirm", "gate": "operator approved at turn 5", "turns": 5, "cost_usd": 0.0}
```

`ts`, `evidence`, `autonomy`, `gate`, `turns` and `cost_usd` are populated by
`agent.py`'s loop right before the gated call (`_dispatch`, tracking
`self._evidence`, the current step, and `_current_cost()`), and read by
`issue_decision_letter` at write time — see `tools.py`. `evidence`
collapses repeated tool names the same way the brief's own example does
(`"check_coverage x3"`). `cost_usd` is `0.0` above because this is the
scripted backend (no tokens spent, by design — see D5(a)); the same record
from a live model carries the real measured value instead, computed at
write time from `config.PRICE_PER_MILLION` — the same pricing table
`harness.py`'s own reporting uses (moved to `config.py` precisely so both
read one source rather than risking two copies drifting apart), rounded to
four decimal places, `0.0` for any model not in that table rather than a
guess.

An earlier draft of this document deliberately left `cost_usd` out of this
file, reasoning that a stale price should never be able to write a wrong
dollar figure into an append-only business record. That is a real risk,
and the mitigation kept here is the single-source-of-truth pricing table
above, not silence: `config.py` is now the one place a price can be wrong,
and both `decisions.jsonl` and every harness/report number would be wrong
together rather than silently disagreeing with each other — which is a
better failure mode than one file being right and the other wrong.

**Two field names are kept as this project's own, not renamed to the
brief's literal example.** The brief's own text frames that example as
"something of this shape," not a schema to copy verbatim, so:
- `claim_id`, not `case_id` — every other file in this repository
  (`expected_outcomes_A.json`, `scripts_A.py`, `tools.py`'s own tool
  signatures, `harness.py`'s code check) already calls this field
  `claim_id`; renaming just this one record's key to match the brief's
  generic illustrative term would make it the one place in the codebase
  that disagreed with the domain's own name for the same value.
- `detail`, not `reason` — the brief's example carries a single
  human-written sentence; this record carries a structured object
  (`line_dispositions`, `approved_total`, `trigger`, `missing_document`,
  depending on the decision) that is strictly richer and is what D0(c)'s
  "traceable to a record" test and D4's `must_record` answer keys actually
  check against. Collapsing it to one sentence would lose information the
  rest of this project's evaluation depends on, in exchange for a closer
  textual match to an illustrative example.

## Verification

```
$ python3 harness.py --case CLM-8850 --verbose
$ python3 harness.py --case CLM-8888 --verbose
$ python3 harness.py --case CLM-8910 --verbose
$ python3 harness.py --case CLM-8842 --json /tmp/one_row.json   # the AgentResult record above
$ cat decisions.jsonl                                            # the gated record above, appended live
```
