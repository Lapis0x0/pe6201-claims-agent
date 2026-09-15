"""Reconstruct historical decision records from already-committed live-battery
result files, without calling any model.

logs/decisions.jsonl is append-only, and it always was for the write path
inside tools.py - only harness.py and guardrail_checklist.py used to wipe it
at the START of every run, which is why no run's history survived the next
one. Nothing in this script talks to OpenRouter, imports LiveBackend, reads
OPENROUTER_API_KEY, or otherwise makes a network call - it only reads JSON
files already committed under results/ and normalizes them into the same
record shape tools.py's gated write already produces.

Two kinds of source, handled differently because they are genuinely
different shapes, not because the data means something different:

1. `decisions_audit.jsonl` (repo root) - a copy of decisions.jsonl exactly
   as it stood after the gpt-4o-mini v2 (90-trial) live battery, saved by
   hand before the next battery's run would otherwise have overwritten it.
   Already in the native gated-decision-record shape (ts, claim_id,
   decision, detail, evidence, autonomy, gate, turns, cost_usd) - this is
   RICHER than what any results/*.json row carries (it has the real
   evidence list and gate string), so it is used as-is for gpt-4o-mini v2,
   in preference to reconstructing that same battery a second time from
   results/d2b_live_v2_gpt4o_mini.json.

2. Every other canonical live battery (results/d5b_live_*.json and the
   gpt-4o-mini v1 prompt pass, results/d2b_live_v1_gpt4o_mini.json) has no
   native decisions.jsonl capture - only harness.py's own per-trial JSON
   export survives. Each row there carries enough to reconstruct a
   decision record (case_id, decision, detail, turns, tokens, cost,
   guardrails_fired) but NOT everything the native shape has (no evidence
   tool-call list, no gate/autonomy string, no timestamp) - those fields
   are written as null, never invented, per the one rule this script
   cannot bend.

The model/source-file registry is imported from d6_cost_model.RUNS, the
same registry every other report figure and the cost model itself already
use - this script cannot silently drift from what "gpt-4o-mini" or
"deepseek-v4-flash" means anywhere else in the repository.

Idempotent: every record's identity key is
    (model, prompt_version, case_id, trial, source_file, record_origin)
Existing logs/decisions.jsonl lines are read first and kept exactly as
they are; only records whose identity key is not already present get
appended. Running this script twice adds zero new lines the second time.

Usage: python3 scripts/build_decisions_from_existing_runs.py
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)  # so `import config`, `from d6_cost_model import RUNS` resolve

import config
from d6_cost_model import RUNS

RESULTS_DIR = os.path.join(ROOT, "results")
DECISIONS_AUDIT_PATH = os.path.join(ROOT, "decisions_audit.jsonl")

# gpt-4o-mini v2's battery has a native decisions_audit.jsonl capture that
# is richer than its results/*.json row export - use that instead of
# reconstructing the same battery twice from two different sources.
NATIVE_CAPTURE_SKIP = {"gpt-4o-mini"}


def _identity(record):
    return (record.get("model"), record.get("prompt_version"),
            record.get("case_id"), record.get("trial"),
            record.get("source_file"), record.get("record_origin"))


def _load_existing(path):
    if not os.path.exists(path):
        return [], set()
    records = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    seen = {_identity(r) for r in records if "record_origin" in r}
    return records, seen


def from_native_audit():
    """decisions_audit.jsonl - already in the native record shape. Adds
    model/prompt_version/trial (trial inferred by counting this claim_id's
    prior occurrences in THIS file, in order - a real structural fact
    about the file, not an invented one) and provenance fields, without
    altering any existing field's value."""
    if not os.path.exists(DECISIONS_AUDIT_PATH):
        return []
    seen_per_claim = {}
    out = []
    with open(DECISIONS_AUDIT_PATH, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            native = json.loads(line)
            claim_id = native["claim_id"]
            seen_per_claim[claim_id] = seen_per_claim.get(claim_id, 0) + 1
            trial = seen_per_claim[claim_id]
            out.append({
                "ts": native.get("ts"),
                "case_id": claim_id,
                "decision": native.get("decision"),
                "detail": native.get("detail"),
                "evidence": native.get("evidence"),
                "autonomy": native.get("autonomy"),
                "gate": native.get("gate"),
                "model": "openai/gpt-4o-mini",
                "prompt_version": "v2",
                "trial": trial,
                "turns": native.get("turns"),
                "tool_calls": None,
                "tokens_in": None,
                "tokens_out": None,
                "cost_usd": native.get("cost_usd"),
                "latency_seconds": None,
                "guardrails_fired": None,
                "stopped_by": None,
                "record_origin": "native_decisions_log",
                "source_file": "decisions_audit.jsonl",
            })
    return out


def from_harness_results(label, model, filename, prompt_version):
    """One results/*.json harness row export - reconstruct a decision
    record for every trial that actually reached the gated write
    (letter_issued=True). Fields the row genuinely does not carry (the
    tool-call evidence list, the gate/autonomy strings, a timestamp) are
    left null, never guessed."""
    path = os.path.join(RESULTS_DIR, filename)
    if not os.path.exists(path):
        return []
    rows = json.loads(open(path, encoding="utf-8").read())
    out = []
    for row in rows:
        if not row.get("letter_issued"):
            continue  # no gated write happened in this trial - nothing to reconstruct
        out.append({
            "ts": None,
            "case_id": row.get("case_id"),
            "decision": row.get("actual"),
            "detail": row.get("detail"),
            "evidence": None,
            "autonomy": None,
            "gate": None,
            "model": model,
            "prompt_version": prompt_version,
            "trial": row.get("trial"),
            "turns": row.get("steps"),
            "tool_calls": row.get("tool_calls"),
            "tokens_in": row.get("prompt_tokens"),
            "tokens_out": row.get("completion_tokens"),
            "cost_usd": row.get("cost_usd"),
            "latency_seconds": row.get("runtime_seconds"),
            "guardrails_fired": row.get("guardrails_fired"),
            "stopped_by": row.get("stop_reason"),
            "record_origin": "reconstructed_from_harness_results",
            "source_file": "results/" + filename,
        })
    return out


def collect_all():
    records = from_native_audit()
    for label, (model, filename) in RUNS.items():
        if label in NATIVE_CAPTURE_SKIP:
            continue
        prompt_version = "v1" if "v1 prompt" in label else "v2"
        records.extend(from_harness_results(label, model, filename, prompt_version))
    return records


def main():
    existing, seen = _load_existing(config.DECISIONS_PATH)
    candidates = collect_all()

    new_records = [r for r in candidates if _identity(r) not in seen]
    # Guard against duplicate candidates within this same run, too.
    dedup_new = []
    added_this_run = set()
    for r in new_records:
        key = _identity(r)
        if key in added_this_run:
            continue
        added_this_run.add(key)
        dedup_new.append(r)

    os.makedirs(config.LOGS_DIR, exist_ok=True)
    if dedup_new:
        with open(config.DECISIONS_PATH, "a", encoding="utf-8") as fh:
            for r in dedup_new:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    total_after, _ = _load_existing(config.DECISIONS_PATH)

    print("Historical records available to reconstruct: {}".format(len(candidates)))
    print("Already present in {}: {}".format(config.DECISIONS_PATH, len(existing)))
    print("Newly appended this run: {}".format(len(dedup_new)))
    print("Total records now: {}".format(len(total_after)))
    print()
    by_model = {}
    for r in total_after:
        if "record_origin" not in r:
            continue  # a pre-existing scripted-run record, not from this script
        key = (r.get("model"), r.get("prompt_version"))
        by_model[key] = by_model.get(key, 0) + 1
    for (model, version), count in sorted(by_model.items()):
        print("  {:<32} {:<4} {} records".format(model or "?", version or "?", count))

    write_snapshot(total_after)


def write_snapshot(records):
    """logs/decisions.json - a readable, consolidated snapshot generated
    FROM decisions.jsonl. Not a second source of truth: regenerating it
    never rewrites decisions.jsonl itself, only reads it."""
    models = sorted({r["model"] for r in records if r.get("model")})
    snapshot = {
        "generated_from": "logs/decisions.jsonl",
        "record_count": len(records),
        "models": models,
        "records": records,
    }
    with open(config.DECISIONS_SNAPSHOT_PATH, "w", encoding="utf-8") as fh:
        json.dump(snapshot, fh, indent=2, ensure_ascii=False)
    print("\nWrote {} records to {}".format(len(records), config.DECISIONS_SNAPSHOT_PATH))


if __name__ == "__main__":
    main()
