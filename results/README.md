# Results — committed evidence, not regenerated on the fly

Everything in this folder is the literal output of a run, kept so the
numbers in the `docs/*.md` write-ups are checkable against something concrete
rather than asserted. All of it is reproducible for free except where
named.

| File | Produced by | What it is |
|---|---|---|
| `harness_scripted_default.json` | `python3 harness.py --json results/harness_scripted_default.json` | The canonical D5(a) run: 90 trials (30 ordinary × 1 + 20 negative × 3), scripted, parallel calling. 100% pass. |
| `guardrail_checklist.json` | `python3 guardrail_checklist.py --json results/guardrail_checklist.json` | All 12 D3(b) cases, scripted. 12/12. |
| `d2c_scripted_parallel.json`, `d2c_scripted_sequential.json` | `python3 harness.py --json ...` / `--sequential --json ...` | The two D2(c) control arms, per-run rows (steps, tool_calls, tokens), 50 cases each, 1 trial. |
| `d2c_measured_exact.json` | `python3 measure_parallel.py --json ...` | The exact (simulated-replay, not closed-form) per-case token measurement behind `d2c_measurement.md`. |
| `d5b_live_smoke_CLM-8842.json` | `python3 harness.py --live --model openai/gpt-4o-mini --case CLM-8842 --json ...` | One live smoke-test run, kept as early evidence real tokens/turns diverge from the scripted assumption. |
| `d2b_live_v1_gpt4o_mini.json`, `d2b_live_v2_gpt4o_mini.json` | `harness.py --live --descriptor-version ...` | Canonical D2(b) descriptor control arms: same model, current 50-case set, 90 trials, descriptor version changed, return shape held fixed. `v1` uses `descriptors_v1.py` — see `d2b_descriptor_rewrite.md`. |
| `d2b_return_shape_v1_gpt4o_mini.json`, `d2b_return_shape_v2_gpt4o_mini.json` | `harness.py --live --descriptor-version v2 --return-shape-version ...` | Canonical D2(b) return-shape control arms: same model, same 50-case set, 90 trials, descriptor pinned at v2 in both, only `check_coverage`'s actual return value changed (prose vs typed JSON). 63/90 (70.0%) vs 67/90 (74.4%) — see `d2b_return_shape.md`. |
| `d5b_live_gemini_2.5_flash.json`, `d5b_live_deepseek_v4_flash.json`, `d5b_live_llama_3.1_8b_instruct.json`, `d5b_live_qwen_2.5_7b_instruct.json` | `harness.py --live --model ...` | Canonical D5(b) batteries. Together with the canonical GPT-4o-mini v2 file above, these are five models, current 50-case set, 90 trials each. Re-measurement moved the ranking: `deepseek-v4-flash` is now first (98.9%), overtaking `gemini-2.5-flash` (93.3%) — see `d5b_live_battery.md`. |
| `judgement_checks.json` | independent semantic review using `../docs/judgement_check_prompt.md` | D4 judgement checks, pass 1: selected Gemini live records, GPT-5 grader, 2/10, with date and per-case rationales. |
| `judgement_checks_gpt4o_mini.json` | independent semantic review using `../docs/judgement_check_prompt.md` | D4 judgement checks, pass 2: selected gpt-4o-mini v2 live records (the model the report leads with), Claude Sonnet 5 grader, 0/10 — see `d4_judgement_checks.md` for why. Combined with pass 1: 2/20. |
| `judgement_recheck2_gemini.json`, `judgement_recheck2_gpt4o_mini.json`, `judgement_recheck2_deepseek.json` | `harness.py --live --model ... --trials 1 --negative-trials 1 --case ...` (one trial, same case ids as the two passes above; DeepSeek re-uses the Gemini set) | Follow-up live re-run of the same 20 judgement-check cases after `tools.check_decision_gate` was strengthened to require a cited, cross-checked record id and a minimum-substance basis (no bare-id citations) in escalate/approval/request_document writes. 30 live calls, cheap tier. |
| `judgement_checks_after_fix_v2.json` | independent semantic review of the three files above, same rubric | D4 judgement checks, follow-up pass: Claude Sonnet 5 grader, 2026-09-13. Combined Gemini+GPT-4o-mini 2/20 → 9/20 (Gemini 2/10→4/10, GPT-4o-mini 0/10→5/10); DeepSeek 7/10 fresh, no prior baseline. Two disclosed side effects (a Gemini regression on one case, a new GPT-4o-mini false-positive narrative-injection pattern on two cases) — see `d4_judgement_checks.md`'s follow-up section. |
| `d5b_live_gpt4o_mini_full_battery.json`, `d5b_live_validation_after_fix.json`, `d5b_live_validation_after_prompt_fix.json` | earlier `harness.py --live` runs | Superseded exploratory/debugging runs; excluded from D5 and D6. |
| `d2c_scripted_measured_current.json` | `python3 measure_parallel.py --json ...` | Current per-case token measurement — supersedes `d2c_measured_exact.json` above. |
| `decisions_live_gpt4o_mini_sample.jsonl` | copied from a live `harness.py --live --model openai/gpt-4o-mini` run's `decisions.jsonl` | A permanent, committed example of the gated action's own persisted record — same shape D1 documents (`ts`, `evidence`, `autonomy`, `gate`, `turns`, real `cost_usd`), 90 records from the current 50-case set. `decisions.jsonl` itself stays git-ignored (it's a run output, truncated and rewritten by every `harness.py`/`guardrail_checklist.py` run — see `d1_sample_traces.md`), so this is the stable audit copy: what a real live decision record actually looks like, without a re-run overwriting it. |

## Cost so far (all live files above)

~$2.25 total across the smoke test, the live batteries (all five
D5(b) models, the D2(b) descriptor v1/v2 pair, and the D2(b) return-shape
v1/v2 pair, current 50-case set), and the judgement-check gate-fix
follow-up (30 single-trial live calls, three models, ~$0.13 for the
evidence kept below — an earlier, superseded gate-strengthening pass cost
a further ~$0.12 and is not part of the current committed evidence)
— comfortably inside the $3/member and $10 course-wide budget lines.

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
