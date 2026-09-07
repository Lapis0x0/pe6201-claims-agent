# Contributions

**Team B-9 · Section B · PE6201 A2**

The split below is what the team agreed. The status column records what has
actually landed in this repository, and is updated as work merges — it is not a
statement of intent.

| Member | Deliverables owned | Status |
|---|---|---|
| SHI ZHIYUN | Agent architecture: ReAct loop, code guardrails, gated action, scripted backend, trajectories, harness, and live-battery configuration. | Landed and verified: the 40-case scripted set passes 80/80 trials; code-layer guardrails and multi-action parsing execute successfully. |
| UBAIDULLA ASMITHA | Tool layer, six-field descriptor contracts and poka-yoke, D2(a) pruning, D2(b) v1 comparison, notebooks, and D2(c) work with Shi Zhiyun. | Landed and verified: six shipped tools, measured descriptor control arms, and the parallel/sequential experiment are committed. |
| JIANG DONG | D0 justification and D3(b) guardrail checklist. | Landed and verified: D0 contains the measured reliability arithmetic; the scripted checklist passes 12/12, including three hostile-text cases. |
| LIU WEIQI | D6 three-layer cost model, four-lever ledger, sensitivity analysis, break-even calculation, and cap economics. | Landed and verified: `d6_cost_model.py` reproduces D6 from canonical live result files using the FAQ-defined trial pass rate. |
| NIU DUOER | D4 evaluation set and D7 reproducible failures; consolidation of team-authored cases. | Landed and verified: 40 labelled isolated cases, 20 negative cases, and two working/broken/restored failure reproductions. |
| XU LIANGJUAN | Final report and demonstration; D2(b) write-up support and live-model evidence. | Repository-side D2(b) and live-result evidence has landed. Report and demonstration status is maintained outside this repository audit. |
| Everyone | Five to eight evaluation cases each and participation in final live measurements/demonstration. | The consolidated 40-case set and five-model-plus-v1 evidence have landed. Individual case/model ownership must match the signed declaration and commit history. |

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
