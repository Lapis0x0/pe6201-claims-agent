# Results — committed evidence, not regenerated on the fly

Everything in this folder is the literal output of a run, kept so the
numbers in the `d*.md` write-ups are checkable against something concrete
rather than asserted. All of it is reproducible for free except where
named.

| File | Produced by | What it is |
|---|---|---|
| `harness_scripted_default.json` | `python3 harness.py --json results/harness_scripted_default.json` | The canonical D5(a) run: 80 trials (20 ordinary × 1 + 20 negative × 3), scripted, parallel calling. 100% pass. |
| `guardrail_checklist.json` | `python3 guardrail_checklist.py --json results/guardrail_checklist.json` | All 12 D3(b) cases, scripted. 12/12. |
| `d2c_scripted_parallel.json`, `d2c_scripted_sequential.json` | `python3 harness.py --json ...` / `--sequential --json ...` | The two D2(c) control arms, per-run rows (steps, tool_calls, tokens), 40 cases each, 1 trial. |
| `d2c_measured_exact.json` | `python3 measure_parallel.py --json ...` | The exact (simulated-replay, not closed-form) per-case token measurement behind `d2c_measurement.md`. |
| `d5b_live_smoke_CLM-8842.json` | `python3 harness.py --live --model openai/gpt-4o-mini --case CLM-8842 --json ...` | One live smoke-test run, kept as early evidence real tokens/turns diverge from the scripted assumption. |
| `d5b_live_validation_after_prompt_fix.json` | `python3 harness.py --live --model openai/gpt-4o-mini --negative-trials 1 --json ...` | **Current D5(b) result.** 40 cases, 1 trial each: 67.5% case-level pass rate. Failure analysis in `d5b_live_battery.md`. |
| `d5b_live_gpt4o_mini_full_battery.json`, `d5b_live_validation_after_fix.json` | earlier `harness.py --live` runs | Superseded by the file above; kept only as an intermediate record. |
| `d2c_scripted_measured_current.json` | `python3 measure_parallel.py --json ...` | Current per-case token measurement — supersedes `d2c_measured_exact.json` above. |

## Cost so far (all live files above)

~$0.6 total across the smoke test and the live batteries — comfortably
inside the course budget.

## Multi-model comparison — deliberately deferred to the team

D5(b)'s required 3+-model comparison, and D2(b)'s v1-vs-v2 live pass, are
**not** being run further on this one key. Two models spanning price tiers
were smoke-tested as candidates for whoever on the team picks this up next
(`deepseek/deepseek-chat`, cheap tier, confirmed working; `gemini-2.5-pro`
was ruled out — it's a reasoning model, and one single-turn smoke test used
3,479 hidden "thinking" tokens, exactly what the brief warns against for
this assignment) — neither run was kept as committed evidence since they
were just naming/cost checks, not part of the battery. The team declaration
already assigns one model per member; continuing solo would spend shared
key budget on work the team plan accounts for. See
`d5b_live_battery.md`'s "Multi-model comparison — deferred to the team"
section.

## Regenerating

Every file except the live ones costs nothing and needs no key:

```bash
python3 harness.py --json results/harness_scripted_default.json
python3 harness.py --sequential --json results/d2c_scripted_sequential.json
python3 measure_parallel.py --json results/d2c_measured_exact.json
python3 guardrail_checklist.py --json results/guardrail_checklist.json
```
