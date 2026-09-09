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
| 5. Orchestrator-workers | No | The branching here is observation-dependent within a single agent's loop (which checks fire depends on what earlier ones return), not an unpredictable *fan-out into independent subtasks* that would benefit from splitting the work across separate workers — so a coordination layer would add cost without addressing a real parallel-decomposition need. |
| 6. Evaluator-optimiser | No | There's no "first draft, then a critique pass" shape here — the routing rule is fixed and deterministic once the facts are known; a second pass over the same facts finds nothing new. |
| **7. Agent** | **Yes** | The model decides, at runtime, which check to run next based on what the last one returned, and stops with one of three outcomes once — not before — the evidence supports it. |

**The four-question test, applied:**

| Question | Answer for Problem A |
|---|---|
| Who decides the sequence, and when? | The model, at runtime — `lookup_member_policy` first is fixed, but everything after depends on what it returns. |
| Does step count vary with the input? | **Yes, measured**: our 50-case evaluation set runs 3–6 turns per claim under parallel calling (median 5). `CLM-8910` (a lapsed policy) finishes in 3 turns; `CLM-9000` (a five-line claim) takes 5 turns but 9 tool calls; a request-document case with a preauth chase (`CLM-8985`) takes 6. |
| Can every path be enumerated? | No — we test outcomes (does it reach `approve_in_principle`/`request_document`/`escalate` correctly), not the specific tool sequence, because which lines need `get_preauthorisation` depends on the claim. |
| What does it cost? | Unpredictable until capped — `config.MAX_STEPS`/`MAX_TOOL_CALLS` bound it. D7 derived those caps from the measured turn distribution (`n=50, median=5, min=3, max=6, 0/50 hit the 15-turn cap`) rather than leaving them at their inherited defaults — see `d7_failures.md`. |

**The two conditions, both required.** An agent is a system where the model dynamically directs its own process and tool usage; take away either of the following two conditions and it stops being one:

- *The steps are not known in advance.* True here: the ReAct loop's next tool call is chosen at runtime from what the previous observation returned — `config.SYSTEM_PROMPT` states a dependency rule (establish eligibility first, batch what is independent, never call a dependent tool before its arguments have been observed), not a fixed call order, and the four traces below show the actual sequence differing by claim.
- *It gets ground truth back at every step, so reality can correct it.* Also true: every `Observation` line in the trace comes from a real lookup against `data_A/` (policy status, coverage rules, pre-authorisation records), never from the model's own prior text. Without this the loop would be a monologue — fluent and self-consistent, but unfalsifiable, since nothing outside the model's own output could ever contradict it.

Both conditions hold for Problem A, which is what actually puts it on rung 7 rather than the claim alone that "the brief said so."

**The three-question governance-cliff test.** The cliff is not retrieval → agentic retrieval; every tool in this system so far (`lookup_member_policy`, `check_duplicate`, `check_coverage`, `check_hospital`, `get_preauthorisation`) is read-only, which alone would only earn "agentic retrieval." The cliff is agentic retrieval → agent, at the first write:

| | Who picks what to retrieve? | Can it loop and re-query? | Can it change the world? |
|---|---|---|---|
| Retrieval (RAG) | our code — one fixed query | no — a single pass | no — read-only |
| Agentic retrieval | the model, at runtime | yes — it re-queries on what it finds | no — read-only |
| **This system** | the model, at runtime | yes | **YES — `issue_decision_letter` writes one JSON record to `decisions.jsonl`** |

`issue_decision_letter` is that first irreversible action, and it is the entire reason the autonomy gate (D3(a)) sits immediately in front of that one function rather than around the agent as a whole: everything before it is read-only and freely retryable, and everything after it is a committed decision.

Four concrete traces, from the shipped 50-case set (`d4_case_notes.md` has all 50) — short, long, and early-exit kept as three *distinct* cases rather than folded together:

- **Short** (`CLM-8850`, `single_line_short_run`, `approve_in_principle`): one line, nothing unusual — 5 turns, 5 tool calls. Short because there is little to check, not because anything cut the run off.
- **Long, multi-line** (`CLM-9000`, five line items, `approve_in_principle`): 5 turns, 9 tool calls — `lookup_member_policy` and `check_duplicate` run alone, then `check_hospital` plus five independent `check_coverage` calls batch into a single turn, then the decision letter.
- **Early-exit** (`CLM-8910`, `policy_lapsed`): `lookup_member_policy` returns a lapsed status → the agent escalates immediately, 3 turns, 2 tool calls. No line is ever priced, because a lapsed policy will not pay them regardless — shorter than the "short" case above, and for a different reason.
- **Request-document, with a dependency** (`CLM-8888`, `preauth_absent`): `check_coverage` on one line returns `requires_preauth: yes`, which is the only reason `get_preauthorisation` gets called at all; it finds no record, so the run asks for a named authorisation rather than guessing — 6 turns, 8 tool calls. A claim with the same shape but no line requiring pre-authorisation would finish a turn earlier, because that dependent call would never fire.

## D0(b) — When not to build an agent

**Ground-truth test.** Problem A has fast and objective sources of truth that can contradict the model: the policy row gives status and validity dates; procedure and coverage records determine whether each line is covered; pre-authorisation records determine whether a required authorisation is valid on the service date; the hospital record gives panel status; and the policy record gives the remaining annual limit. These local lookups return machine-checkable evidence within seconds. This makes a grounded loop possible. If the task instead depended only on slow or subjective feedback, such as customer satisfaction, we would use a fixed workflow with a human gate rather than unsupervised autonomy.

**Arithmetic test.** A long trajectory compounds per-step error. If a run required 20 steps and each step succeeded with probability 0.95, the probability that every step was correct would be approximately `0.95^20 = 0.36`. The practical responses are to improve the weak step, reduce the number of steps, and make failure recoverable through a request or escalation.

`s = P^(1/T)` needs two real numbers, `P` (whole-run pass rate) and `T`
(median turns). Our scripted pass rate (100%, 50/50) is **not** usable as
`P`: the scripted backend replays a hand-written *correct* trajectory for
every case by construction, so it checks that the harness and the tool
layer agree with each other, not how often a real model gets a step right.

D5(b)'s live battery (`openai/gpt-4o-mini`, full write-up in
`d5b_live_battery.md`) supplies both values from the same 90 live trials:

```
P = 0.6667 (60/90 trials passed), T = 8 (median turns)
s = 0.6667^(1/8) ~= 0.951
```

An implied ~95.1% per-step reliability compounding over 8 turns produces the
measured 66.67% trial-level run-success rate. Pairing `P` and `T` from the same
distribution avoids treating the scripted backend's median as a live-model
measurement. D7 reports the scripted median separately for cap calibration.
Holding that same inferred `s`
fixed and varying `T`, as Capsule 1's own worked example does, shows how
much of the loss is turn count rather than step quality: a shorter,
4-turn run predicts `s^4 ~= 81.6%`, while a longer, 12-turn run predicts
`s^12 ~= 54.4%` — the same per-step reliability, but predicted run success
ranging from roughly 54% to 82% depending on turn count alone, either side
of the measured `T=8` point (66.7%). This is Way
2 (cut the number of steps) made concrete: it is the same lever D2(c)'s
parallel calling already pulls on the scripted trajectories (median 5
turns, down from a longer sequential equivalent), and the reason cutting
turns further is worth attempting even where step quality itself cannot
be improved. Grouping the 30 failing trials by
case family (15 distinct failing cases out of 50) gives a broader picture
than an earlier pass on the smaller 40-case set suggested: failures
cluster into **three** areas, not two. Pre-authorisation handling is now
the largest single cluster — `preauth_absent`, `preauth_absent_different_member`,
`preauth_absent_knee_arthroscopy`, `preauth_expired` and
`preauth_expired_boundary` account for 5 of the 15 failing families.
Narrative-injection resistance is the second cluster, and it widened: all
four injection shapes (`prompt_injection_overt`,
`prompt_injection_imitating_tool_output`, `prompt_injection_fake_authority`,
`prompt_injection_skip_check`) now fail at least one trial each, not only
the subtler "imitating a tool result" case an earlier, smaller-set pass
had flagged as the standout. Annual-limit arithmetic is the third,
unchanged from before (`annual_limit_exceeded`,
`annual_limit_exceeded_boundary`). A handful of single-trial ordinary-case
misses (`five_line_wide_claim`, `four_line_all_covered_variety`,
`required_document_absent`, `required_document_absent_second_member`) sit
outside these three clusters and, at `n=1` each, are not distinguishable
from live run-to-run noise on this evidence alone. That answers this
section's question directly, with a wider net than the earlier
measurement gave: **our bigger problem is step quality concentrated in
three identifiable areas — pre-authorisation checks, injection resistance,
and limit arithmetic — not step count in general**, and not the two
narrower steps an earlier, smaller-set measurement pointed at. Cutting
turns further would not fix any of the three.

**Two different moves, not the same lever.** Class 4 names two ways to
raise a low `P`, and they are not interchangeable: (a) *fix the step* —
a better descriptor, a filtered return, a tighter type — which raises `s`
directly; or (b) *remove or bypass the step* — cut the tool, fold it into
a parallel turn, move the work into ordinary code — which lowers `T`
instead. Because a weak step usually depresses `s` and inflates `T`
together (a poor observation invites re-reading and retrying), the two
moves are easy to conflate, but they attack different terms in
`s = P^(1/T)` and only one of them is available for each of our three
weak spots:

- **Pre-authorisation handling** (the largest cluster) is move (a) only.
  `get_preauthorisation` is a required, business-mandated check for any
  line flagged `requires_preauth: yes` — it cannot be cut or bypassed
  without silently approving claims that need authorisation, so the only
  lever here is a better descriptor or a tighter prompt clause
  distinguishing "no record" from "record present but expired," the
  distinction the current failures blur.
- **Narrative-injection resistance** is also move (a) only, for the same
  reason: the untrusted-narrative guardrail is a prompt instruction, not
  a tool call, so there is no step to remove — only a clause to sharpen
  (see `d5b_live_battery.md`'s finding that the prompt does not yet warn
  against a narrative *imitating the shape of a tool's own output*).
- **Annual-limit arithmetic**, by contrast, is a step D2(c) already
  applied move (b) to: batching `check_hospital` with every independent
  `check_coverage` call is exactly "fold it into a parallel turn," and it
  is the reason turn count fell 21.8% (`d2c_measurement.md`). It did not
  fix the arithmetic itself — the limit comparison still happens inside
  the model's own reasoning between observations, not in code — so this
  cluster's residual failures show move (b)'s ceiling: cutting turns
  helped cost and latency, not this specific judgement.

The honest read: **two of our three weak spots only have move (a)
available**, which is the harder lever Class 4 warns about — D2(b)'s
corrected v1-vs-v2 result (+2.3pp from a better `check_coverage`
descriptor) is a small, real proof that move (a) works here, but it also
shows how much smaller its yield is than move (b)'s D2(c) result (21.8%
token cut, effectively free). Problem A's bigger failures are step-quality
problems precisely because they are checks that cannot be designed away.

### The third test: the bill

The third test asks whether the value of one completed task exceeds the token cost
of a run divided by how often it works. The slide says this denominator must
be the negative-case rate, not the happy-path rate. Using measured API token
usage and the 60 negative trials per model, rather than the slide's illustrative
`B=1,000`, `D=300`, and `$3/$15 per million`:

`C_completed = C_run / p`

| Model | Negative trials passed | Measured C/run | C/completed output |
|---|---:|---:|---:|
| deepseek-v4-flash | 59/60 (98.3%) | $0.00122 | $0.00124 |
| gemini-2.5-flash | 54/60 (90.0%) | $0.00566 | $0.00629 |
| gpt-4o-mini | 32/60 (53.3%) | $0.00314 | $0.00589 |
| qwen-2.5-7b-instruct | 25/60 (41.7%) | $0.00203 | $0.00488 |
| llama-3.1-8b-instruct | 20/60 (33.3%) | $0.00088 | $0.00265 |

The completed-output threshold is below one cent for every tested model, so
the token-only completed-task test is passed whenever a useful completed first
response is worth more than the corresponding value in the last column.
The cheapest raw run is not automatically the cheapest useful output: Llama
has the lowest C/run of any model ($0.00088) but its low negative-case
reliability (33.3%) triples its cost per completion ($0.00265) — the
sharpest reliability penalty in the table, ahead of Qwen's near-doubling
($0.00203 to $0.00488).

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
