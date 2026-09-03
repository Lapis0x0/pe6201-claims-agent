# Contributions

**Team B-9 · Section B · PE6201 A2**

The split below is what the team agreed. The status column records what has
actually landed in this repository, and is updated as work merges — it is not a
statement of intent.

| Member | Deliverables owned | Status |
|---|---|---|
| SHI ZHIYUN | Agent architecture: the ReAct loop (`agent.py`), the code-level guardrails (D3a), the gated action and its gate, the scripted backend and the recorded trajectories, the evaluation harness. D5 model-battery configuration. | Skeleton landed: loop, tools, backends, trajectories, harness. Scripted set passes 15/15. |
| UBAIDULLA ASMITHA | The tool layer (`tools.py`): reviewing and hardening the reference implementations, the six-field descriptor contracts and their poka-yoke (D2b), the D2a tool-pruning analysis, and the parallel-call work with Shi Zhiyun (D2c). | Reference implementations in place and marked as such in `tools.py`. Descriptor fields (`guardrail`, `cost`) stubbed in `config.TOOL_SPECS` for completion. |
| JIANG DONG | D0 justification (ladder placement, ground-truth and arithmetic tests, the five success criteria) and the D3b guardrail checklist — ten checks, at least three against hostile free text, all run on the scripted backend. | D0 landed (`d0_justification.md`). D3b outstanding; the caps and the gate it exercises are in place. |
| LIU WEIQI | D6 cost model: the three-layer cost-to-serve formula, four levers with before/after, the ±10pp sensitivity band, break-even success rate, and three caps. Problem A inputs: 8,000 claims/month, US$7.60 failure cost. | Outstanding. `LiveBackend` records prompt and completion tokens per run so the model rests on measured numbers. |
| NIU DUOER | D4 evaluation set (40 cases, 8 negative) and D7, the two reproducible failures. Sets the grading standard and consolidates the cases everyone writes. | Outstanding. The harness applies the code check and prints the judgement sheet; new cases go through `make_fixtures_A.py` plus a hand-written label. |
| XU LIANGJUAN | The 2,000-word report and the five-minute demo, including the negative case it must show. Writes up the D2b tool descriptors. | Outstanding. |
| Everyone | Five to eight evaluation cases each, to Niu Duoer. Everyone speaks in the demo. | Outstanding. |

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
