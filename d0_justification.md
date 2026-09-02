# D0 — Why Problem A Needs an Agent

## Chosen problem and scope

Our team chose Problem A: health-insurance claim first response. The system receives a claim and must reach one of three outcomes: approve in principle, request a specific missing document, or escalate to a human claims assessor. The system reads local fixture records only. Its gated action is `issue_decision_letter`: a simulated, irreversible business action represented by one structured record appended to a local file. It does not send a real letter or modify a live insurance system.

## D0(a) — Ladder placement

Our system is placed on rung 7 of the Class 4 ladder: a single-agent ReAct system. A single model call cannot reliably answer the claim because the answer depends on records that are not contained in the request, including policy status and dates, line-item coverage, pre-authorisation validity, hospital status, and remaining annual limit. A fixed prompt chain is also insufficient. The number and order of checks vary by claim: one claim may contain one line item while another contains several; only some procedures require pre-authorisation; a lapsed policy or an exceeded annual limit should cause an early escalation instead of further line-by-line processing. A routing model can choose an initial lane, but later tool results can change the correct route. Parallel calls reduce waiting time for independent checks, but parallelisation alone still requires the checks to be known in advance and cannot decide which new query is needed after an observation.

An orchestrator-worker or evaluator-optimiser design would add complexity and cost, and multi-agent execution is outside the A2 scope. A ReAct agent is appropriate because the model chooses the next tool at runtime, receives an observation grounded in a system-of-record, and can continue, stop, request a document, or escalate based on that observation. The first governance cliff is the call to `issue_decision_letter`: it writes the final decision record. Therefore the autonomy gate belongs immediately before that function, rather than only around the whole agent.

## D0(b) — When not to build an agent

**Ground-truth test.** Problem A has fast and objective sources of truth that can contradict the model: the policy row gives status and validity dates; procedure and coverage records determine whether each line is covered; pre-authorisation records determine whether a required authorisation is valid on the service date; the hospital record gives panel status; and the policy record gives the remaining annual limit. These local lookups return machine-checkable evidence within seconds. This makes a grounded loop possible. If the task instead depended only on slow or subjective feedback, such as customer satisfaction, we would use a fixed workflow with a human gate rather than unsupervised autonomy.

**Arithmetic test.** A long trajectory compounds per-step error. If a run required 20 steps and each step succeeded with probability 0.95, the probability that every step was correct would be approximately `0.95^20 = 0.36`. The practical responses are to improve the weak step, reduce the number of steps, and make failure recoverable through a request or escalation. After the evaluation set supplies the measured whole-run pass rate `P` and the failure analysis supplies the median turn count `T`, we will estimate the implied per-step reliability as `s = P^(1/T)`. For example, if a provisional run achieved `P = 0.78` at `T = 6`, then `s = 0.78^(1/6) ≈ 0.959`; this is a diagnostic illustration, not a substitute for our measured result. We will replace it with the recorded D4/D7 values before final submission.

## D0(c) — What counts as a good run

1. The outcome and its stated cause are traceable to the relevant claim, policy, procedure, hospital, and pre-authorisation records.
2. The final decision is consistent with the fixed Problem A routing rules, including partial payment and excluded line items.
3. The gated action is executed at most once and only after the required autonomy gate has been satisfied.
4. When the records do not support a decision, the agent names the exact missing document or escalates to the human assessor instead of inventing an answer.
5. The run records its evidence trail, turn count, and cost, and stays within the configured step and budget caps.
