# D5(a) — reproducibility, not a model experiment

D5(a) isn't a comparison of anything — it's a single hard requirement the
brief states directly: `BACKEND="scripted"` must be the default, need no
key, cost nothing, and produce the same result on a clean run every time.
This is what makes the scripted backend usable as ground truth for D1–D4
and D7: those deliverables would be meaningless if two runs of the same
harness against the same cases could silently disagree.

## The test

Two independent, back-to-back invocations of the full 40-case set:

```
$ python3 harness.py --json /tmp/run_a.json
$ python3 harness.py --json /tmp/run_b.json
$ diff /tmp/run_a.json /tmp/run_b.json
```

`diff` reports differences on 80 lines out of ~2,800 — every one of them
the `runtime_seconds` field (real wall-clock timing, which is
instrumentation, not part of the decision — see D1's field table). Every
other field, for every one of the 80 trial rows (`decision`, `detail`,
`trigger`, `steps`, `tool_calls`, `letter_issued`, `trace`,
`guardrails_fired`), is unchanged:

```python
a = json.load(open("/tmp/run_a.json")); b = json.load(open("/tmp/run_b.json"))
for r in a: r.pop("runtime_seconds", None)
for r in b: r.pop("runtime_seconds", None)
a == b   # True
```

## Why this holds by construction

The scripted backend (`ScriptedBackend`) doesn't call a model at all — it
replays a hand-written, fixed sequence of `Call`/`Final` turns from
`scripts_A.PLANS`, one script per case, matched by `claim_id`. There is no
sampling, no network call, and `config.DEFAULT_TEMPERATURE = 0` doesn't
even apply here (that setting only affects `LiveBackend`). Determinism
isn't something the scripted path achieves — it's what it *is*: a fixed
script cannot produce a different transcript on a second read.

**No API key, no network, and no cost**, confirmed the same way every
other scripted evidence file in this repository is: `python3 harness.py`
runs to completion with no `--live` flag and no key in the environment.

## Verification

```
$ python3 harness.py --json /tmp/run_a.json
$ python3 harness.py --json /tmp/run_b.json
$ diff /tmp/run_a.json /tmp/run_b.json    # only runtime_seconds differs
```
