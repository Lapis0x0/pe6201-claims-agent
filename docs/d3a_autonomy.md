# D3(a) — the autonomy setting, made real

Until this pass, `"autonomy": "confirm"` existed only as a **descriptive
string** written into decision records — nothing in `tools.py` or `agent.py`
read it or changed behaviour because of it. That's fixed: the setting is now
enforced inside `tools.check_decision_gate`, in front of the one
irreversible step (`issue_decision_letter`), exactly where the brief asks
for it — not in front of the whole agent.

## The three settings (`config.AUTONOMY_SETTINGS`)

| Setting | What the gate does | Who ends the run |
|---|---|---|
| `suggest` | Always refuses the write. `issue_decision_letter` returns `GATE REFUSED: autonomy is 'suggest'...` every time. | The agent — it still reaches a Final Answer with its recommended decision; the loop's autonomy check (`agent._finalise`) does not require a letter to exist in this mode. |
| `confirm` (**shipped default**) | Writes only if `ClaimsTools.operator_approved` is `True`. | The agent, once approved — matches the brief's own FAQ example (`if autonomy == "confirm" and not operator_approved(claim_id): return "BLOCKED"`). |
| `act` | Writes immediately; no approval needed. | The agent, unconditionally. |

`operator_approved` simulates whatever a real deployment would use to know
a human signed off (a dashboard click, a Slack approval) — there is no UI
in this system (out of scope, D1's scope boundary), so it is a constructor
argument on `ClaimsTools`. The harness and all 40 evaluation cases pass
`True` by default (a human has already reviewed, the ordinary case this
system is built for); one guardrail case (`G11`) passes `False` to prove
the gate actually blocks when that hasn't happened yet.

## Why `confirm`, defended against the other two

- **Not `suggest`.** At 8,000 claims/month (Appendix A's volume), a human
  who must personally record every clean approval hasn't been given an
  agent — they've been given a very literate typist. The whole point of
  automating the first response is lost if a person re-types the outcome
  for every claim, including the ones with nothing wrong.
- **Not `act`.** This problem's gated action tells a member "approved in
  principle" — walking that back is expensive (D0's own framing). Combine
  that with D3(b)'s hostile-text cases: the claim narrative is free text
  from someone outside the organisation, and the agent's evidence trail
  can look clean even when the narrative tried to manipulate it. A cheap,
  fast human sign-off in front of exactly one step (not the whole run) is
  worth the latency it costs, precisely because the failure mode it
  catches is rare but expensive, not frequent and cheap.
- **`confirm` is the narrowest gate that still stops the expensive
  mistake.** It doesn't slow down evidence-gathering, tool calls, or the
  reasoning — only the one line that can't be taken back.

## Verified behaviour, all three modes

```
ACT mode     -> decision: approve_in_principle  letter_issued: True   (operator_approved was False - no confirmation needed)
SUGGEST mode -> decision: approve_in_principle  letter_issued: False  stop_reason: final_answer (concludes without writing)
CONFIRM mode -> see guardrail case G11: blocked on attempt 1 (no approval yet), recorded on attempt 2 (approved in between)
```

## What this changed in the code

- `config.py`: `AUTONOMY_SETTINGS = ("suggest", "confirm", "act")`,
  `AUTONOMY = "confirm"`.
- `tools.py`: `ClaimsTools.__init__` takes `autonomy` and
  `operator_approved`; `check_decision_gate` refuses in `suggest` mode
  unconditionally, and in `confirm` mode until `operator_approved` is set.
- `agent.py`: `_finalise`'s autonomy check is now
  `if self.tools_obj.autonomy != "suggest" and not self.tools_obj.letter_issued`
  — `suggest` mode is allowed to conclude without ever writing.
- `guardrail_checklist.py`: new case **G11**
  (`confirm_mode_blocks_without_operator_approval`), bringing the checklist
  to 12/12 (above the 10-case floor; G12 — invalid arguments — was added
  separately, see `d3b_guardrail_checklist.md`).

## Verification

```
$ python3 harness.py               # unaffected: 40/40 (default operator_approved=True)
$ python3 guardrail_checklist.py   # 12/12, including G11
```
