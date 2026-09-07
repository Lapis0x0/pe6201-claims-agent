# D0 — Why Problem A Needs an Agent

## Chosen problem and scope

Our team chose Problem A: health-insurance claim first response. The system receives a claim and must reach one of three outcomes: approve in principle, request a specific missing document, or escalate to a human claims assessor. The system reads local fixture records only. Its gated action is `issue_decision_letter`: a simulated, irreversible business action represented by one structured record appended to a local file. It does not send a real letter or modify a live insurance system.

## D0(a) — Ladder placement

Our system is placed on rung 7 of the Class 4 ladder: a single-agent ReAct system. A single model call cannot reliably answer the claim because the answer depends on records that are not contained in the request, including policy status and dates, line-item coverage, pre-authorisation validity, hospital status, and remaining annual limit. A fixed prompt chain is also insufficient. The number and order of checks vary by claim: one claim may contain one line item while another contains several; only some procedures require pre-authorisation; a lapsed policy or an exceeded annual limit should cause an early escalation instead of further line-by-line processing. A routing model can choose an initial lane, but later tool results can change the correct route. Parallel calls reduce waiting time for independent checks, but parallelisation alone still requires the checks to be known in advance and cannot decide which new query is needed after an observation.

An orchestrator-worker or evaluator-optimiser design would add complexity and cost, and multi-agent execution is outside the A2 scope. A ReAct agent is appropriate because the model chooses the next tool at runtime, receives an observation grounded in a system-of-record, and can continue, stop, request a document, or escalate based on that observation. The first governance cliff is the call to `issue_decision_letter`: it writes the final decision record. Therefore the autonomy gate belongs immediately before that function, rather than only around the whole agent.

**Rungs 1–6, and what each would have missed on this problem:**

| Rung | Would it work here? | Why not |
|---|---|---|
| 1. Single call | No | The claim alone doesn't carry policy status, coverage, pre-authorisation validity, hospital panel status, or the remaining annual limit — none of that is in the request. |
| 2. Prompt chain | No | The number and order of checks is decided by what earlier checks return (a lapsed policy skips line pricing entirely; a line needing pre-authorisation triggers a lookup the others never do) — a fixed chain can't branch on its own output. |
| 3. Routing | No | A single upfront lane (e.g. "simple" vs "complex" claim) can't be corrected once a later tool result changes the right path — three of our shipped cases (`CLM-8910`, `8917`, `8925`) end the run after one lookup, which a router would have to know in advance to route correctly. |
| 4. Parallelisation | Partial | Batching independent calls (D2(c)) cuts turns by 21% measured — real, and we use it — but it only re-groups calls whose need was already known; it can't decide a *new* query is needed after seeing an observation. |
| 5. Orchestrator-workers | No | Would add a coordination layer and cost for a task that is one linear sequence of gated checks, not an unpredictable fan-out of independent subtasks. |
| 6. Evaluator-optimiser | No | There's no "first draft, then a critique pass" shape here — the routing rule is fixed and deterministic once the facts are known; a second pass over the same facts finds nothing new. |
| **7. Agent** | **Yes** | The model decides, at runtime, which check to run next based on what the last one returned, and stops with one of three outcomes once — not before — the evidence supports it. |

**The four-question test, applied:**

| Question | Answer for Problem A |
|---|---|
| Who decides the sequence, and when? | The model, at runtime — `lookup_member_policy` first is fixed, but everything after depends on what it returns. |
| Does step count vary with the input? | **Yes, measured**: our 40-case evaluation set runs 3–6 turns per claim under parallel calling (median 5). `CLM-8910` (a lapsed policy) finishes in 3 turns; `CLM-9000` (a five-line claim) takes 5 turns but 9 tool calls; a request-document case with a preauth chase (`CLM-8985`) takes 6. |
| Can every path be enumerated? | No — we test outcomes (does it reach `approve_in_principle`/`request_document`/`escalate` correctly), not the specific tool sequence, because which lines need `get_preauthorisation` depends on the claim. |
| What does it cost? | Unpredictable until capped — `config.MAX_STEPS`/`MAX_TOOL_CALLS` bound it, and D7 will re-derive those caps from the measured turn distribution rather than leaving them at their inherited defaults. |

Four concrete traces, from the shipped 40-case set (`d4_case_notes.md` has all 40) — short, long, and early-exit kept as three *distinct* cases rather than folded together:

- **Short** (`CLM-8850`, `single_line_short_run`, `approve_in_principle`): one line, nothing unusual — 5 turns, 5 tool calls. Short because there is little to check, not because anything cut the run off.
- **Long, multi-line** (`CLM-9000`, five line items, `approve_in_principle`): 5 turns, 9 tool calls — `lookup_member_policy` and `check_duplicate` run alone, then `check_hospital` plus five independent `check_coverage` calls batch into a single turn, then the decision letter.
- **Early-exit** (`CLM-8910`, `policy_lapsed`): `lookup_member_policy` returns a lapsed status → the agent escalates immediately, 3 turns, 2 tool calls. No line is ever priced, because a lapsed policy will not pay them regardless — shorter than the "short" case above, and for a different reason.
- **Request-document, with a dependency** (`CLM-8888`, `preauth_absent`): `check_coverage` on one line returns `requires_preauth: yes`, which is the only reason `get_preauthorisation` gets called at all; it finds no record, so the run asks for a named authorisation rather than guessing — 6 turns, 8 tool calls. A claim with the same shape but no line requiring pre-authorisation would finish a turn earlier, because that dependent call would never fire.

## D0(b) — When not to build an agent

**Ground-truth test.** Problem A has fast and objective sources of truth that can contradict the model: the policy row gives status and validity dates; procedure and coverage records determine whether each line is covered; pre-authorisation records determine whether a required authorisation is valid on the service date; the hospital record gives panel status; and the policy record gives the remaining annual limit. These local lookups return machine-checkable evidence within seconds. This makes a grounded loop possible. If the task instead depended only on slow or subjective feedback, such as customer satisfaction, we would use a fixed workflow with a human gate rather than unsupervised autonomy.

**Arithmetic test.** A long trajectory compounds per-step error. If a run required 20 steps and each step succeeded with probability 0.95, the probability that every step was correct would be approximately `0.95^20 = 0.36`. The practical responses are to improve the weak step, reduce the number of steps, and make failure recoverable through a request or escalation.

`s = P^(1/T)` needs two real numbers, `P` (whole-run pass rate) and `T`
(median turns). Our scripted pass rate (100%, 40/40) is **not** usable as
`P`: the scripted backend replays a hand-written *correct* trajectory for
every case by construction, so it checks that the harness and the tool
layer agree with each other, not how often a real model gets a step right.

D5(b)'s live battery (`openai/gpt-4o-mini`, full write-up in
`d5b_live_battery.md`) supplies the real measured numbers:

```
P = 0.6875 (55/80 trials passed), T = 7 (median turns)
s = 0.6875^(1/7) ~= 0.948
```

An implied ~95% per-step reliability compounding over 7 turns produces the
measured 68.75% trial-level run-success rate — the exact arithmetic this test argues in
the abstract, now measured on our own system rather than illustrated with
the brief's numbers. Grouping the failing runs by which step precedes them
(D0(b)'s own suggested method) points at two specific, nameable weak
steps — a narrative-injection classifier and the annual-limit
comparison — rather than a generally unreliable agent. That answers this
section's question directly: **our bigger problem is step quality on a
small number of specific steps, not step count in general** — cutting
turns further would not fix either of those two steps.

### The third test: the bill

The third test asks whether the value of one completed task exceeds the token cost
of a run divided by how often it works. The slide says this denominator must
be the negative-case rate, not the happy-path rate. Using measured API token
usage and the 60 negative trials per model, rather than the slide's illustrative
`B=1,000`, `D=300`, and `$3/$15 per million`:

`C_completed = C_run / p`

| Model | Negative trials passed | Measured C/run | C/completed output |
|---|---:|---:|---:|
| gemini-2.5-flash | 57/60 (95.0%) | $0.00591 | $0.00622 |
| deepseek-v4-flash | 53/60 (88.3%) | $0.00120 | $0.00136 |
| gpt-4o-mini | 37/60 (61.7%) | $0.00311 | $0.00504 |
| qwen-2.5-7b-instruct | 26/60 (43.3%) | $0.00205 | $0.00474 |
| llama-3.1-8b-instruct | 30/60 (50.0%) | $0.00104 | $0.00209 |

The completed-output threshold is below one cent for every tested model, so
the token-only completed-task test is passed whenever a useful completed first
response is worth more than the corresponding value in the last column.
The cheapest raw run is not automatically the cheapest useful output: Qwen's
lower reliability almost doubles its token cost per completion.

This is a diagnostic for a **retry-until-success** world. D6 correctly uses
the assignment's Class 5 **escalate-on-failure** world instead:
`C_run + (1-p) x $7.60`. We report both because they answer different
questions; we do not add them together. The calculation and
`../figs/fig_d0_class4_bill_test.png` reproduces with `python3 generate_plots.py`.

## D0(c) — What counts as a good run

1. The outcome and its stated cause are traceable to the relevant claim, policy, procedure, hospital, and pre-authorisation records.
2. The final decision is consistent with the fixed Problem A routing rules, including partial payment and excluded line items.
3. The gated action is executed at most once and only after the required autonomy gate has been satisfied.
4. When the records do not support a decision, the agent names the exact missing document or escalates to the human assessor instead of inventing an answer.
5. The run records its evidence trail, turn count, and cost, and stays within the configured step and budget caps.
