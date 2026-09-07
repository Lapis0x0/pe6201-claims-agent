# D2(a) — The tool set, chosen not collected

Every tool the agent can call, scored against Class 4's three questions. The
driver is discriminability and evidence, not headcount.

| Tool | Does a task fail without it? | Could the model confuse it with a neighbour? | What it costs when never called | Verdict |
|---|---|---|---|---|
| `get_claim` | **No.** `config.format_claim_prompt()` already puts the full claim — member id, hospital id, date of service, documents, every line item, and the narrative — in the first user message. Nothing downstream needs to re-fetch it. **Evidence**: across all 15 shipped scripted trajectories, `get_claim` is called **zero times** (`grep get_claim scripts_A.py` inside every `PLANS` entry returns nothing). | Yes, in the harmful direction: a re-read tool sitting next to a claim the model already has in context invites a wasted first turn that adds nothing. | Its six-field descriptor sat in the prompt prefix `B`, re-sent and re-billed on every turn of every run, called or not. | **Cut.** Removed from `config.TOOL_SPECS` and from `tools.ClaimsTools.as_dict()`/the class body. Re-run after the cut: `python3 harness.py` still reports 15/15 — proof the tool was never load-bearing. |
| `lookup_member_policy` | Yes. The only source of policy status, validity dates, the pre-computed remaining annual limit, and exclusions. Three of the shipped `escalate` families (`policy_lapsed`, `outside_policy_dates`, `annual_limit_exceeded`) and every exclusion decision depend on it. | No — no other tool returns policy data, and it is the mandatory first call (the gate itself checks `policy_looked_up`). | Called on 15/15 shipped cases. | Keep. |
| `check_coverage` | Yes. The only source of per-line exclusion status, whether a pre-authorisation is required, and which supporting document a line needs. | No — distinct from `get_preauthorisation`: this tells you a preauth is *required*, not whether one *exists*. | Called once per line item (a 4-line claim calls it 4 times). | Keep. |
| `get_preauthorisation` | Yes. The only source of whether a pre-authorisation record exists and whether it is valid on the date of service. Two of the three shipped `request_document` families depend on it. | No, for the same reason as above — the pairing with `check_coverage` is a hand-off, not an overlap. | Called only for lines `check_coverage` flagged `requires_preauth: yes` — the prompt tells the model not to call it otherwise. | Keep. |
| `check_hospital` | Yes, for D0(c)'s "outcome traceable to the records" test: panel status must be recorded in the decision even though it never changes the decision on its own. Without it, an approval would rest on an incomplete record. | No. | Called once per claim. | Keep — the closest call of the six, kept because the task statement requires panel status be *recorded*, not merely available. |
| `check_duplicate` | Yes. The only source of prior-decision history. Without it a resubmitted claim would be silently re-approved — a real financial exposure, not a cosmetic gap. One of the six shipped `escalate` families depends on it entirely. | No. | Called once per claim, before line pricing. | Keep. |
| `issue_decision_letter` | Yes — it is the gated action itself; the whole point of the run. | No. | Called exactly once per claim, last. | Keep. |

## The cut, in the format the brief asks for

**Before**: 7 tools in `config.TOOL_SPECS` / `tools.ClaimsTools.as_dict()`.
**After**: 6. `get_claim` removed from both, and its method deleted from
`tools.py` rather than left dead.
**What this makes impossible**: a turn that reads data the model was already
given, at the cost of one tool descriptor's worth of prompt-prefix tokens on
every turn of every run. It also shrinks the interface surface the guardrail
layer and the evaluation set have to cover by one tool that was never
exercised — a failure mode we would otherwise be carrying untested.
**Feeds D6**: removing `get_claim`'s descriptor shrinks the prompt prefix `B`
used in `D6`'s lever-1 (tool block size) before/after comparison — measured
exactly (not estimated) at **-96 tokens/turn** in isolation (1,996 → 1,900
tokens for a 7-tool vs 6-tool prompt, both with stub descriptors, holding
everything else constant). This isolated delta is stable even as the
absolute numbers move with later prompt edits — see `d6_notes.md`'s "Lever 1,
split into its two real causes" for the full reconciliation against D2(b)'s
opposite-direction effect and the current absolute figures.

## One move we tried, and did not take

Considered widening `check_coverage` to accept a list of procedure codes, so
one call could price every line on a claim instead of one call per line.
**Rejected**: D2(c)'s parallel-call batching already collapses N independent
per-line `check_coverage` calls into a single turn (they don't depend on each
other), which gets the same turn-count benefit `check_coverage(codes: list)`
would have bought — without giving up the per-line disposition trail the
decision letter's `line_dispositions` field needs, and without a signature
change that would have touched every shipped scripted trajectory. Moving the
work into the tool's argument list here would have traded a documented,
inspectable batching rule (D2c) for an opaque one hidden inside a single call.

## Verification

```
$ python3 harness.py
...
pass rate: 100.0%  (80/80 runs; 20 ordinary cases x 1 trial + 20 negative cases x 3 trials)
supplementary strict case-consistency rate: 40/40 (100.0%)
```
Unchanged from before the cut, as expected — no shipped trajectory ever called
`get_claim`, including all 25 cases added later under D4.
