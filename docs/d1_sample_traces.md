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

## One instrumented decision record, in full

`CLM-8842` (the brief's own partly-payable worked example), as it actually
appears once every field above is filled in from a real run:

```json
{
  "case_id": "CLM-8842",
  "decision": "approve_in_principle",
  "steps": 6,
  "tool_calls": 8,
  "prompt_tokens": 0,
  "completion_tokens": 0,
  "cost_usd": 0.0,
  "runtime_seconds": 0.00031,
  "guardrails_fired": [],
  "letter_issued": true,
  "detail": {
    "approved_total": 2180,
    "refused_total": 300,
    "hospital": "H-114 Riverside General, on panel",
    "policy": "POL-3310 active 2026-04-01 to 2027-03-31, 9,200 remaining",
    "line_dispositions": [
      {"code": "47120", "amount": 1400, "disposition": "approved", "basis": "covered by POL-3310; no pre-authorisation required"},
      {"code": "62480", "amount": 780, "disposition": "approved", "basis": "covered by POL-3310; PA-5521 valid 2026-08-01 to 2026-10-31 authorises the date of service 2026-09-02; discharge_summary supplied"},
      {"code": "31255", "amount": 300, "disposition": "refused", "basis": "excluded by POL-3310 under EX-14 cosmetic dermatology"}
    ],
    "narrative_check": "no instruction found in the member narrative"
  }
}
```

`prompt_tokens`/`completion_tokens`/`cost_usd` are 0 here because this is
the scripted backend (by design — see D5(a)); the same record from a live
model carries real measured values in those three fields instead, with
every other field unchanged in shape.

## Verification

```
$ python3 harness.py --case CLM-8850 --verbose
$ python3 harness.py --case CLM-8888 --verbose
$ python3 harness.py --case CLM-8910 --verbose
$ python3 harness.py --case CLM-8842 --json /tmp/one_row.json   # the record above, in full
```
