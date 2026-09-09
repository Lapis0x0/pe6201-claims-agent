# D4 judgement-check rubric

## Grader

- Grader: OpenAI Codex (GPT-5), independent of every model in the D5 battery
- Review date: 2026-09-07
- Input: the first Gemini 2.5 Flash trial's `detail` record and the answer key's
  `must_record` requirements
- Output: PASS only when the record semantically supports every requirement;
  otherwise FAIL with the unsupported requirement named

## Prompt

You are grading a health-insurance first-response decision record. Compare the
candidate `detail` object with every item in `must_record`. Judge meaning, not
substring overlap. A requirement passes only when the candidate provides the
specific fact and enough context to support it. Do not infer a missing fact
from the expected answer. Return `PASS` or `FAIL`, followed by one concise
rationale. This is a prose/evidence judgement only; decision, trigger, line
identifier, totals, and gated-action count are graded separately in code.

## Sampling rule

Ten cases were selected to cover all three outcomes and the
main prose-risk shapes: multi-line disposition, near-duplicate explanation,
missing and expired authorisation, early escalation, duplicate evidence, and
three hostile-narrative variants. The grader is not one of the five models
being evaluated in D5(b).

## Second pass

A second, independent pass applied this same rubric to ten more cases -
disjoint from the first ten, same three-outcome/prose-risk-shape spread -
against `results/d2b_live_v2_gpt4o_mini.json`, the canonical gpt-4o-mini v2
run (the model the report actually leads with, not just the D5(b) top
performer). Grader: Claude Sonnet 5, independent of every D5(b) model and of
the first pass's grader. Review date: 2026-09-10. See
`results/judgement_checks_gpt4o_mini.json` and `d4_judgement_checks.md`.
