# D2(a) — The tool set, chosen not collected

Every tool the agent can call, scored against Class 4's three questions. The
driver is discriminability and evidence, not headcount.

The third column is deliberately the prompt-prefix cost of the tool's own
rendered descriptor block — the `signature`/`what`/`returns`/`use-it` text
`render_tool_list()` sends on every turn regardless of whether the tool is
actually called that run — not how often the tool happens to be invoked
(an earlier draft of this table conflated the two; call frequency answers a
different, less relevant question, since the prefix cost is paid whether or
not any given run ever calls the tool). Measured directly from
`config.TOOL_SPECS` via `render_tool_list()`'s own block-construction logic,
at the repository's standard `ceil(chars/4)` token estimate:

| Tool | Does a task fail without it? | Could the model confuse it with a neighbour? | What it costs when never called (its own rendered descriptor block, paid every turn regardless) | Verdict |
|---|---|---|---|---|
| `get_claim` | **No.** `config.format_claim_prompt()` already puts the full claim — member id, hospital id, date of service, documents, every line item, and the narrative — in the first user message. Nothing downstream needs to re-fetch it. **Evidence**: across all 50 shipped scripted trajectories, `get_claim` is called **zero times** (`grep get_claim scripts_A.py` inside every `PLANS` entry returns nothing). | Yes, in the harmful direction: a re-read tool sitting next to a claim the model already has in context invites a wasted first turn that adds nothing. | Before the cut, its stub descriptor's own block cost ~96 tokens of the prompt prefix on every turn, called or not — see the isolated Lever-1 measurement below. | **Cut.** Removed from `config.TOOL_SPECS` and from `tools.ClaimsTools.as_dict()`/the class body. Re-run after the cut: `python3 harness.py` still reports 50/50 — proof the tool was never load-bearing. |
| `lookup_member_policy` | Yes. The only source of policy status, validity dates, the pre-computed remaining annual limit, and exclusions. Three of the shipped `escalate` families (`policy_lapsed`, `outside_policy_dates`, `annual_limit_exceeded`) and every exclusion decision depend on it. | No — no other tool returns policy data, and it is the mandatory first call (the gate itself checks `policy_looked_up`). | 161 tokens/turn — its own rendered block is 643 chars, paid on every turn of every run whether or not that run needs a policy lookup (it always does, but the cost itself does not depend on that). | Keep. |
| `check_coverage` | Yes. The only source of per-line exclusion status, whether a pre-authorisation is required, and which supporting document a line needs. | No — distinct from `get_preauthorisation`: this tells you a preauth is *required*, not whether one *exists*. | 152 tokens/turn — its own rendered block is 607 chars. This is the tool D2(b) targets precisely because that fixed per-turn cost compounds fastest here (once per line item, not once per claim). | Keep. |
| `get_preauthorisation` | Yes. The only source of whether a pre-authorisation record exists and whether it is valid on the date of service. Two of the three shipped `request_document` families depend on it. | No, for the same reason as above — the pairing with `check_coverage` is a hand-off, not an overlap. | 161 tokens/turn — its own rendered block is 644 chars, paid every turn even on the majority of runs that never actually need a pre-authorisation lookup. | Keep. |
| `check_hospital` | Yes, for D0(c)'s "outcome traceable to the records" test: panel status must be recorded in the decision even though it never changes the decision on its own. Without it, an approval would rest on an incomplete record. | No. | 142 tokens/turn — its own rendered block is 565 chars, the cheapest of the six. | Keep — the closest call of the six, kept because the task statement requires panel status be *recorded*, not merely available. |
| `check_duplicate` | Yes. The only source of prior-decision history. Without it a resubmitted claim would be silently re-approved — a real financial exposure, not a cosmetic gap. One of the six shipped `escalate` families depends on it entirely. | No. | 144 tokens/turn — its own rendered block is 573 chars. | Keep. |
| `issue_decision_letter` | Yes — it is the gated action itself; the whole point of the run. | No. | 295 tokens/turn — its own rendered block is 1,180 chars, by far the most expensive of the six, because its `detail` shape has to name every decision-specific required field (`trigger`, `missing_document`/`line`, `line_dispositions` plus totals) so the gate's requirements are legible in the prompt, not just enforced silently in code. | Keep. |

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
exactly (not estimated) at **-96 tokens/turn** in isolation (2,095 → 1,999
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
pass rate: 100.0%  (90/90 runs; 30 ordinary cases x 1 trial + 20 negative cases x 3 trials)
supplementary strict case-consistency rate: 50/50 (100.0%)
```
Unchanged from before the cut, as expected — no shipped trajectory ever called
`get_claim`, including all 35 cases added after the original 15-case
scaffold set (`d4_case_notes.md` has the full 50-case breakdown).
