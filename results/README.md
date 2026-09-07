# Results — committed evidence, not regenerated on the fly

Everything in this folder is the literal output of a run, kept so the
numbers in the `docs/*.md` write-ups are checkable against something concrete
rather than asserted. All of it is reproducible for free except where
named.

| File | Produced by | What it is |
|---|---|---|
| `harness_scripted_default.json` | `python3 harness.py --json results/harness_scripted_default.json` | The canonical D5(a) run: 80 trials (20 ordinary × 1 + 20 negative × 3), scripted, parallel calling. 100% pass. |
| `guardrail_checklist.json` | `python3 guardrail_checklist.py --json results/guardrail_checklist.json` | All 12 D3(b) cases, scripted. 12/12. |
| `d2c_scripted_parallel.json`, `d2c_scripted_sequential.json` | `python3 harness.py --json ...` / `--sequential --json ...` | The two D2(c) control arms, per-run rows (steps, tool_calls, tokens), 40 cases each, 1 trial. |
| `d2c_measured_exact.json` | `python3 measure_parallel.py --json ...` | The exact (simulated-replay, not closed-form) per-case token measurement behind `d2c_measurement.md`. |
| `d5b_live_smoke_CLM-8842.json` | `python3 harness.py --live --model openai/gpt-4o-mini --case CLM-8842 --json ...` | One live smoke-test run, kept as early evidence real tokens/turns diverge from the scripted assumption. |
| `d2b_live_v1_gpt4o_mini.json`, `d2b_live_v2_gpt4o_mini.json` | `harness.py --live --descriptor-version ...` | Canonical D2(b) control arms: same model and 80 trials, descriptor version changed. |
| `d5b_live_gemini_2.5_flash.json`, `d5b_live_deepseek_v4_flash.json`, `d5b_live_llama_3.1_8b_instruct.json`, `d5b_live_qwen_2.5_7b_instruct.json` | `harness.py --live --model ...` | Canonical D5(b) batteries. Together with the canonical GPT-4o-mini v2 file above, these are five models, 80 trials each. |
| `judgement_checks.json` | independent semantic review using `../docs/judgement_check_prompt.md` | D4 judgement checks on selected Gemini live records: 2/10, with grader, date and per-case rationales. |
| `d5b_live_gpt4o_mini_full_battery.json`, `d5b_live_validation_after_fix.json`, `d5b_live_validation_after_prompt_fix.json` | earlier `harness.py --live` runs | Superseded exploratory/debugging runs; excluded from D5 and D6. |
| `d2c_scripted_measured_current.json` | `python3 measure_parallel.py --json ...` | Current per-case token measurement — supersedes `d2c_measured_exact.json` above. |

## Cost so far (all live files above)

~$0.6 total across the smoke test and the live batteries — comfortably
inside the course budget.

## Canonical experiment metadata

`manifest.json` identifies every canonical live run by model, model family,
prompt version, run date, trial count, and primary trial-level pass rate. It
also marks exploratory files as superseded. The result rows predate this
manifest and do not carry all of that run-level context themselves, so the
manifest is the authoritative provenance sidecar.

## Regenerating

Every file except the live ones costs nothing and needs no key:

```bash
python3 harness.py --json results/harness_scripted_default.json
python3 harness.py --sequential --json results/d2c_scripted_sequential.json
python3 measure_parallel.py --json results/d2c_measured_exact.json
python3 guardrail_checklist.py --json results/guardrail_checklist.json
```
