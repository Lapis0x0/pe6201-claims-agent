# Contributions

**Team B-9 · Section B · PE6201 A2**

The split below is what the team agreed. The status column records what has
actually landed in this repository, and is updated as work merges — it is not a
statement of intent.

| Member | Deliverables owned | Status |
|---|---|---|
| SHI ZHIYUN | Agent architecture: ReAct loop, code guardrails, gated action, scripted backend, trajectories, harness, and live-battery configuration. | Landed and verified: the 50-case scripted set passes 90/90 trials; code-layer guardrails and multi-action parsing execute successfully. |
| UBAIDULLA ASMITHA | Tool layer, six-field descriptor contracts and poka-yoke, D2(a) pruning, D2(b) v1 comparison, notebooks, and D2(c) work with Shi Zhiyun. | Landed and verified: six shipped tools, measured descriptor control arms, and the parallel/sequential experiment are committed. |
| JIANG DONG | D0 justification and D3(b) guardrail checklist. | Landed and verified: D0 contains the measured reliability arithmetic; the scripted checklist passes 12/12, including three hostile-text cases. |
| LIU WEIQI | D6 three-layer cost model, four-lever ledger, sensitivity analysis, break-even calculation, and cap economics. | Landed and verified: `d6_cost_model.py` reproduces D6 from canonical live result files using the FAQ-defined trial pass rate. |
| NIU DUOER | D4 evaluation set and D7 reproducible failures; consolidation of team-authored cases. | Landed and verified: 50 labelled isolated cases, 20 negative cases, and two working/broken/restored failure reproductions. |
| XU LIANGJUAN | Final report and demonstration; D2(b) write-up support and live-model evidence. | Repository-side D2(b) and live-result evidence has landed. Report and demonstration status is maintained outside this repository audit. |
| Everyone | Five to eight evaluation cases each and participation in final live measurements/demonstration. | The consolidated 50-case set and five-model-plus-v1 evidence have landed. Case ownership is itemised below; it must match the commit history and the signed declaration. |

## Evaluation-case ownership

35 of the 50 cases are team-written (the other 15 are the course-supplied
starting set in `CLAIMS` — kept, not edited, per the rule in
`make_fixtures_A.py`). Every member owns at least 5, grouped by the kind of
judgement call each case tests rather than split arbitrarily:

| Member | Case IDs owned | Count | What the group tests |
|---|---|---|---|
| SHI ZHIYUN | CLM-8980, CLM-8985, CLM-8990, CLM-8995, CLM-9045, CLM-9135 | 6 | Multi-line / interface-stress approvals: independent lines, a preauth-plus-document combination, non-panel multi-line, a second exclusion instance, a second four-line run, a third three-line run |
| NIU DUOER | CLM-9000, CLM-9050, CLM-9055, CLM-9060, CLM-9065, CLM-9070 | 6 | The widest claim in the set, plus all five `request_document` cases: pre-authorisation absent, expired, and two required-document-absent instances |
| LIU WEIQI | CLM-9005, CLM-9010, CLM-9015, CLM-9020, CLM-9040, CLM-9120 | 6 | Boundary and limit cases: pre-authorisation and policy start/end dates treated inclusively, the largest single-line approval, and two claims against the tightest-limit policy |
| JIANG DONG | CLM-9075, CLM-9080, CLM-9085, CLM-9090, CLM-9095, CLM-9100 | 6 | All six `escalate` additions: a second lapsed policy, a second true duplicate, the annual-limit boundary case, and two further hostile-narrative shapes (fake authority, skip-check instruction) |
| UBAIDULLA ASMITHA | CLM-9025, CLM-9030, CLM-9035, CLM-9105, CLM-9110, CLM-9125 | 6 | Short/minimal runs, a preauth valid at a non-panel hospital, a mixed preauth-plus-plain-line claim, and three of the ten cases added to reach the 50-case ceiling |
| XU LIANGJUAN | CLM-9115, CLM-9130, CLM-9140, CLM-9145, CLM-9150 | 5 | The remaining five cases added to reach the 50-case ceiling: non-panel document-required claims, a policy-specific (not procedure-specific) exclusion check, a second preauth-plus-document combination, and the smallest claim in the set |

Every row above resolves against `expected_outcomes_A.json` and has a
recorded trajectory in `scripts_A.py`; `python3 harness.py` passes 90/90 with
the full set. This table is the team's own division for the contribution
log — if it does not match who actually designed which case, correct the
names here before submission; the case IDs and family groupings are accurate
regardless of whose name sits next to them.

## Adding evaluation cases

Do not edit any shipped row. Add yours to the `EXTRA_*` lists at the bottom of
`make_fixtures_A.py`, regenerate, and write the label into
`expected_outcomes_A.json` **by hand, from the routing rules, before running the
agent**. A label copied from the agent's own output measures nothing.

```bash
python3 make_fixtures_A.py
python3 check_my_data.py
# add the label to expected_outcomes_A.json
python3 check_my_data.py
```

A new case also needs a recorded trajectory in `scripts_A.py` if it is to run
under the scripted backend.
